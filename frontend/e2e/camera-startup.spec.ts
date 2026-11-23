import {test,expect} from '@playwright/test';
import {existsSync} from 'node:fs';
import {basename,resolve} from 'node:path';

const faceModel=resolve('../training/artifacts/camera-regression/face_landmarker.task');
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browserPath=process.env.ATTENTION_BROWSER_PATH || (existsSync(chrome)?chrome:undefined);
test.use({permissions:['camera'],launchOptions:{...(browserPath?{executablePath:browserPath}:{}),args:['--use-fake-device-for-media-stream']}});

test('calibration starts with a stalled affect-model download',async({page})=>{
  test.skip(!existsSync(faceModel),'Optional real face-tracker fixture is not installed');
  let releaseDownload!:()=>void;
  const waiting=new Promise<void>(resolve=>{releaseDownload=resolve;});
  await page.route('**/models/fer/**',async route=>{
    await waiting;
    await route.abort().catch(()=>{});
  });
  await page.route('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm/**',async route=>{
    const filename=basename(new URL(route.request().url()).pathname);
    await route.fulfill({path:resolve('node_modules/@mediapipe/tasks-vision/wasm',filename),contentType:filename.endsWith('.wasm')?'application/wasm':'application/javascript',headers:{'access-control-allow-origin':'*'}});
  });
  await page.route('https://storage.googleapis.com/mediapipe-models/**',route=>route.fulfill({path:faceModel,headers:{'access-control-allow-origin':'*'}}));
  await page.route('**/api/sessions/camera-startup-test**',route=>route.fulfill({json:route.request().url().endsWith('/join')?
    {session_id:'camera-startup-test',student_id:'camera-test-student',device_token:'camera-test-credential'}:
    {session_id:'camera-startup-test',course_name:'Camera startup test',instructor_name:'Test instructor',ended_at:null,students:[]}}));
  try {
    await page.goto('/join?session=camera-startup-test');
    await page.getByRole('checkbox').check();
    await page.getByRole('button',{name:'I Understand and Consent',exact:true}).click();
    await page.getByLabel('Display name',{exact:true}).fill('Camera startup test');
    await page.getByRole('button',{name:'Continue to camera setup',exact:true}).click();
    const start=page.getByRole('button',{name:'Start camera calibration',exact:true});
    await expect(start).toBeVisible();
    await start.click();
    await expect(page.getByRole('heading',{name:'Calibrating',exact:true})).toBeVisible({timeout:30000});
    await expect(page.getByRole('dialog')).toBeVisible();
  } finally {releaseDownload();}
});
