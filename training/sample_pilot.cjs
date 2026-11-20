/** Exploratory engagement-only CNN on a verified DAiSEE sample; not the production affect model. */
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const tf = require('../frontend/node_modules/@tensorflow/tfjs');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function metrics(truth, predicted) {
  const matrix = Array.from({length:4},()=>[0,0,0,0]);
  truth.forEach((v,i)=>matrix[v][predicted[i]]++);
  const accuracy = truth.filter((v,i)=>v===predicted[i]).length/truth.length;
  const f1 = matrix.map((row,i)=>{const tp=row[i],fp=matrix.reduce((sum,r)=>sum+r[i],0)-tp,fn=row.reduce((a,b)=>a+b,0)-tp;return 2*tp+fp+fn?2*tp/(2*tp+fp+fn):0});
  return {clips:truth.length,accuracy,macro_f1:f1.reduce((a,b)=>a+b,0)/4,confusion_matrix:matrix,
    binary_accuracy:truth.filter((v,i)=>(v>=2)===(predicted[i]>=2)).length/truth.length};
}
function clipPredictions(model, data) {
  return data.map(c=>{const t=tf.tensor4d(c.pixels,[c.frames,32,32,3]);const probs=model.predict(t);const means=probs.mean(0);const p=Array.from(means.dataSync());tf.dispose([t,probs,means]);return {clip_id:c.clip.clip_id,subject_id:c.clip.subject_id,split:c.clip.split,label:Number(c.clip.labels.engagement),predicted:p.indexOf(Math.max(...p)),probabilities:p,expected_level:p.reduce((s,v,i)=>s+i*v,0)/3}});
}
async function main(){
 const prepared=path.resolve(process.argv[2]||'training/prepared/sample-pilot-002'),out=path.resolve(process.argv[3]||'training/runs/sample-pilot-001');
 if(fs.existsSync(out)&&fs.readdirSync(out).length)throw Error('Use a new output directory');
 const inventory=JSON.parse(fs.readFileSync(path.join(prepared,'inventory.json')));
 await tf.setBackend('cpu');await tf.ready();
 const data=inventory.clips.map(clip=>{const b=fs.readFileSync(path.join(prepared,clip.prepared_file));if(hash(b)!==clip.prepared_sha256)throw Error('Frame hash mismatch');return {clip,frames:clip.decoded_frames,pixels:Float32Array.from(b,v=>v/255)}});
 const train=data.filter(c=>c.clip.split==='Train'),validation=data.filter(c=>c.clip.split==='Validation');
 const labels=[],values=[];for(const c of train){for(let i=0;i<c.frames;i++)labels.push(Number(c.clip.labels.engagement));values.push(...c.pixels)}
 // Deterministic frame order mixing, restricted to the training partition.
 let seed=42;const order=labels.map((_,i)=>i);for(let i=order.length-1;i>0;i--){seed=(Math.imul(1664525,seed)+1013904223)>>>0;const j=seed%(i+1);[order[i],order[j]]=[order[j],order[i]]}
 const shuffled=new Float32Array(values.length);order.forEach((index,i)=>shuffled.set(values.slice(index*3072,(index+1)*3072),i*3072));
 const x=tf.tensor4d(shuffled,[labels.length,32,32,3]),y=tf.oneHot(tf.tensor1d(order.map(i=>labels[i]),'int32'),4);
 const model=tf.sequential({layers:[
  tf.layers.conv2d({inputShape:[32,32,3],filters:4,kernelSize:3,strides:2,activation:'relu',kernelInitializer:tf.initializers.glorotUniform({seed:42})}),
  tf.layers.maxPooling2d({poolSize:[2,2]}),
  tf.layers.conv2d({filters:8,kernelSize:3,activation:'relu',kernelInitializer:tf.initializers.glorotUniform({seed:43})}),
  tf.layers.flatten(),tf.layers.dense({units:4,activation:'softmax',kernelInitializer:tf.initializers.glorotUniform({seed:44})})]});
 model.compile({optimizer:tf.train.adam(.003),loss:'categoricalCrossentropy'});
 const started=new Date().toISOString(),history=[];let best=-1,bestEpoch=0,bestWeights=[];
 for(let epoch=1;epoch<=30;epoch++){
  const fit=await model.fit(x,y,{epochs:1,batchSize:16,shuffle:false,verbose:0});
  const predictions=clipPredictions(model,validation),score=metrics(predictions.map(p=>p.label),predictions.map(p=>p.predicted));
  history.push({epoch,training_loss:fit.history.loss[0],validation_accuracy:score.accuracy,validation_macro_f1:score.macro_f1});
  if(score.macro_f1>best){best=score.macro_f1;bestEpoch=epoch;tf.dispose(bestWeights);bestWeights=model.getWeights().map(w=>w.clone())}
  console.log(`Epoch ${epoch}/30 loss=${fit.history.loss[0].toFixed(4)} validation_macro_f1=${score.macro_f1.toFixed(4)}`);
 }
 model.setWeights(bestWeights);tf.dispose(bestWeights);fs.mkdirSync(out,{recursive:true});
 await model.save(tf.io.withSaveHandler(async artifacts=>{fs.writeFileSync(path.join(out,'weights.bin'),Buffer.from(artifacts.weightData));fs.writeFileSync(path.join(out,'model.json'),JSON.stringify({format:'layers-model',generatedBy:'TensorFlow.js '+tf.version.tfjs,convertedBy:null,modelTopology:artifacts.modelTopology,weightsManifest:[{paths:['weights.bin'],weights:artifacts.weightSpecs}]},null,2));return {modelArtifactsInfo:{dateSaved:new Date(),modelTopologyType:'JSON'}}}));
 // Test predictions are made once, after checkpoint selection using validation only.
 const splits={};for(const split of ['Train','Validation','Test']){const predictions=clipPredictions(model,data.filter(c=>c.clip.split===split));splits[split]={...metrics(predictions.map(p=>p.label),predictions.map(p=>p.predicted)),predictions}}
 const result={status:'sample_pilot_completed',dataset:'DAiSEE',scope:'Exploratory 12-clip engagement-only CNN; not the full benchmark or the production three-head affect model',started_at:started,completed_at:new Date().toISOString(),seed:42,backend:tf.getBackend(),tfjs_version:tf.version.tfjs,model_parameters:model.countParams(),epochs:30,selected_epoch:bestEpoch,selection:'Highest validation clip-level macro-F1; first epoch retained on ties; held-out test scored after selection',preprocessing:inventory.preprocessing,inventory_sha256:hash(fs.readFileSync(path.join(prepared,'inventory.json'))),weights_sha256:hash(fs.readFileSync(path.join(out,'weights.bin'))),history,splits,limitations:['Four selected training clips, four validation clips, four test clips; not a representative sample','Full-frame 32x32 input; no face crop or pretrained backbone','Validation contains only one subject; background and identity confounding remain possible','No boredom/confusion heads were trained; training confusion labels have only class 0','These scores do not establish deployment readiness or the research hypothesis']};
 fs.writeFileSync(path.join(out,'pilot_report.json'),JSON.stringify(result,null,2));console.log('Selected epoch',bestEpoch,'test metrics',splits.Test);tf.dispose([x,y]);model.dispose();
}
if(require.main===module)main().catch(e=>{console.error(e);process.exit(1)});
module.exports={metrics};
