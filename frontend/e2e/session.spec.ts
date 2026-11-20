import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

async function presentationCapture(page: import("@playwright/test").Page, name: string) {
  const root = resolve("../PROJECT NEW DOCUMENT/FULL DAISEE PROJECT UPDATE/screenshots");
  for (const [mode,width,height] of [["desktop",1280,900],["mobile",390,844]] as const) {
    mkdirSync(resolve(root,mode),{recursive:true});
    await page.setViewportSize({width,height});
    if (name === "04-instructor-console") {
      await page.locator('div[class*="lg:grid-cols-4"]').screenshot({path:resolve(root,mode,`${name}.png`),animations:"disabled"});
    } else {
      await page.screenshot({path:resolve(root,mode,`${name}.png`),animations:"disabled"});
    }
  }
  await page.setViewportSize({width:1280,height:900});
}

test("instructor and mobile student complete session, telemetry, history and export", async ({ browser, page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await presentationCapture(page,"01-home");
  await page.getByRole("button", {name: "Start a Session (Instructor)", exact: true}).click();
  await page.getByLabel("Instructor name", {exact:true}).fill("Integration Lecturer");
  await page.getByLabel("Instructor email", {exact:true}).fill("integration@example.org");
  await page.getByLabel("Course name", {exact:true}).fill("Integration lecture");
  await page.getByRole("button", {name:"Create Session", exact:true}).click();
  await page.waitForURL(/\/console\?session=/);
  await expect(page.getByRole("heading", {name:"Integration lecture", exact:true})).toBeVisible();
  const sid = new URL(page.url()).searchParams.get("session")!;
  const code = (await page.getByRole("button", {name:/Copy join code/}).innerText()).trim();
  const studentContext = await browser.newContext({viewport:{width:390,height:844}});
  try {
    const student = await studentContext.newPage();
    student.on("pageerror", error => errors.push(error.message));
    await student.goto(new URL(page.url()).origin);
    await student.getByRole("button", {name:"Join a Session (Student)",exact:true}).click();
    await student.getByLabel("Session join code",{exact:true}).fill(code);
    await student.getByRole("button",{name:"Join",exact:true}).click();
    await student.waitForURL(/\/join\?session=/);
    await expect(student.getByRole("button",{name:"I Understand and Consent",exact:true})).toBeDisabled();
    await presentationCapture(student,"02-consent");
    await student.getByRole("checkbox").check();
    await student.getByRole("button",{name:"I Understand and Consent",exact:true}).click();
    await student.getByLabel("Display name",{exact:true}).fill("Integration Alias");
    await student.getByRole("button",{name:"Continue to camera setup",exact:true}).click();
    await expect(student.getByRole("heading",{name:"Camera Setup",exact:true})).toBeVisible();
    await presentationCapture(student,"03-camera-setup");
    // Exercise real transport without inventing webcam/calibration success.
    await student.evaluate(async sid => {
      const socket = new WebSocket(`ws://localhost:8000/ws/student/${sid}/${localStorage.getItem(`student:${sid}`)}`,
        ["attention", localStorage.getItem(`device:${sid}`)!]);
      await new Promise<void>((resolve, reject) => {socket.onopen=()=>resolve(); socket.onerror=()=>reject(new Error("Socket failed"));});
      socket.send(JSON.stringify({s_eye:1,s_gaze:1,s_yawn:1,s_affect:0,attention_index:87,quality_flag:"normal",inference_mode:"geometric"}));
      // A validation response guarantees the prior reading transaction has committed.
      socket.send(JSON.stringify({invalid:true}));
      await new Promise<void>(resolve => {socket.onmessage=()=>resolve();});
      socket.close();
    },sid);
    await expect(page.getByText("Integration Alias",{exact:true})).toBeVisible();
    await presentationCapture(page,"04-instructor-console");
    await page.getByRole("button",{name:"End Session",exact:true}).click();
    await page.getByRole("dialog").getByRole("button",{name:"End Session",exact:true}).click();
    await page.waitForURL(/\/history\//);
    await presentationCapture(page,"05-session-history");
    const download = page.waitForEvent("download");
    await page.getByRole("button",{name:"Export CSV",exact:true}).click();
    expect((await download).suggestedFilename()).toMatch(/^session_.*\.csv$/);
    expect(errors).toEqual([]);
  } finally {await studentContext.close();}
});

test("trained DAiSEE assets and measured results are accessible", async ({request,page}) => {
  const response = await request.get("/models/daisee-pilot/metadata.json");
  expect(response.ok()).toBeTruthy();
  const metadata = await response.json();
  expect(metadata.status).toBe("sample_pilot_completed");
  expect(metadata.test).toMatchObject({clips:4,accuracy:0.25});
  expect((await request.get("/models/daisee-pilot/weights.bin")).ok()).toBeTruthy();
  await page.goto("/dataset-review");
  await expect(page.getByRole("heading",{level:1})).toBeVisible();
  await expect(page.getByRole("heading", {name:"DAiSEE trained model results",exact:true})).toBeVisible();
  const trained = await request.get("/models/fer/metadata.json");
  expect(trained.ok()).toBeTruthy();
  expect((await trained.json()).training.status).toBe("fine_tuned");
  const screenshots = resolve("../PROJECT NEW DOCUMENT/FULL DAISEE RESULTS/screenshots");
  mkdirSync(screenshots, {recursive:true});
  await page.setViewportSize({width:1280,height:900});
  await page.screenshot({path:resolve(screenshots,"daisee-full-results-desktop.png"),animations:"disabled"});
  await page.locator('section[aria-labelledby="results-heading"]').screenshot({path:resolve(screenshots,"daisee-test-metrics-desktop.png"),animations:"disabled"});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:resolve(screenshots,"daisee-full-results-mobile.png"),animations:"disabled"});
  await page.setViewportSize({width:390,height:1400});
  await page.locator('section[aria-labelledby="results-heading"]').screenshot({path:resolve(screenshots,"daisee-test-metrics-mobile.png"),animations:"disabled"});
  for (const head of ["engagement","boredom","confusion"]) {
    await page.locator(`section[aria-label="${head} test confusion matrix"]`).screenshot({path:resolve(screenshots,`daisee-${head}-matrix-mobile.png`),animations:"disabled"});
  }
});

test("full three-head model runs in the browser", async ({page}) => {
  test.setTimeout(60000);
  await page.goto("/dataset-review");
  await page.addScriptTag({path:resolve("node_modules/@tensorflow/tfjs/dist/tf.min.js")});
  const predictions = await page.evaluate(`(async () => {
    const tf = window.tf;
    await tf.ready();
    const model = await tf.loadLayersModel('/models/fer/model.json');
    const input = tf.zeros([1,224,224,3]);
    const outputs = model.predict(input);
    try { return await Promise.all(outputs.map(async tensor => Array.from(await tensor.data()))); }
    finally { outputs.forEach(tensor => tensor.dispose()); input.dispose(); model.dispose(); }
  })()`) as number[][];
  expect(predictions).toHaveLength(3);
  for (const values of predictions) {
    expect(values).toHaveLength(4);
    expect(values.every(value=>Number.isFinite(value) && value>=0 && value<=1)).toBeTruthy();
    expect(Math.abs(values.reduce((sum,value)=>sum+value,0)-1)).toBeLessThan(0.0001);
  }
});
