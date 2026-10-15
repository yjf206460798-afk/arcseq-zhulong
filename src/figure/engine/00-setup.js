// ARCSEQ 引擎（浏览器端，Three.js）。由 FIG.01 scene.js 抽出的通用部分：渲染、线条、投影、灯、关节-机构-状态、演出导演、尾焰、后处理、审图。
// 作品数据由 build.mjs 注入（__DATA__），THREE 为内联的全局对象。engine/*.js 按文件名顺序拼进同一个闭包，共享作用域。
// 坐标：米，x 向前、y 向左、z 向上，原点在地面转台轴心。相机固定，转台绕 z 转 −φ（φ 为审图方位角，相机相对机头逆时针）。
// 与 FIG.01 的差别（引擎层，2026-10-15 FIG.02 Z0/Z1）：零件可以是任意多边形网格（Blender GLB 转来），带顶点 AO、UV 细节贴图、自发光；
// 渲染走后处理链（MSAA、选择性发光、录制模式的电影画质）；FIG.01 的歼-20 专用功能（风扇、登机梯、剖开、故障、改装对比）不在引擎里。
  const DATA = __DATA__;
  const THREE = window.THREE;
  THREE.ColorManagement.enabled = false;

  const stage = document.querySelector(".af-stage");
  const canvas = stage.querySelector("canvas");
  const readout = document.querySelector("[data-readout]");
  const still = matchMedia("(prefers-reduced-motion: reduce)");
  const MODES = { silhouette: "剪影", volume: "体积", lines: "线稿" };
  const wrap = (deg) => ((deg % 360) + 360) % 360;
  const rgb = (hex) => new THREE.Color(hex);
  const D2R = Math.PI / 180;
  const clamp01 = (t) => Math.min(1, Math.max(0, t));
  const ease = (t) => t * t * (3 - 2 * t);
  const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
  const smoothStepJs = (a, b, x) => {
    const t = clamp01((x - a) / (b - a));
    return t * t * (3 - 2 * t);
  };
  // 画质档：standard（手机）/ high；录制模式另有 cinema（见 80-post.js）
  const quality = { mode: matchMedia("(max-width:560px)").matches ? "standard" : "high" };
  const lowQuality = () => quality.mode === "standard";
  let quiet = false; // 审图快进时不刷新界面
  let clock = 0; // 演出 / 尾焰 / 灯的时钟（秒）；停机复原时归零

  // ———————————————— 渲染器与相机 ————————————————
  // 画布不开自带抗锯齿：画面先画进多重采样的离屏缓冲（80-post.js），再合成到画布
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: "high-performance", preserveDrawingBuffer: true });
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace; // 色板按 sRGB 原值写出，不做色彩管理换算
  renderer.autoClear = false;

  let E = (DATA.elevation * Math.PI) / 180;
  const { width: W, height: H } = DATA.view;
  const { K, origin } = DATA.fit;
  const camera = new THREE.OrthographicCamera(-origin[0] / K, (W - origin[0]) / K, origin[1] / K, -(H - origin[1]) / K, 0.1, 400);
  const VIEW = new THREE.Vector3();
  const CAM0 = new THREE.Vector3();
  /** 俯仰角（度）：默认 DATA.elevation；审图特写可临时改（例如低机位看机腹）。 */
  function setElevation(deg) {
    E = (deg * Math.PI) / 180;
    camera.up.set(-Math.sin(E), 0, Math.cos(E));
    CAM0.set(Math.cos(E) * 100, 0, Math.sin(E) * 100).add(new THREE.Vector3(...(DATA.aim ?? [0, 0, 0])));
    camera.position.copy(CAM0);
    camera.lookAt(new THREE.Vector3(...(DATA.aim ?? [0, 0, 0])));
    VIEW.set(Math.cos(E), 0, Math.sin(E));
  }
  setElevation(DATA.elevation);
  /** 光随相机：从画面左侧、斜上方来（相机右向 = +y，故光的水平分量为 −y）。 */
  const LIGHT = new THREE.Vector3(0, -1, 1.2).normalize();
  const lightFor = () => LIGHT.set(0, -1, 1.2).applyAxisAngle(new THREE.Vector3(0, 1, 0), DATA.elevation * D2R - E).normalize();

  const scene = new THREE.Scene();
  // 世界矩阵每帧在 draw() 里统一更新一次
  scene.matrixWorldAutoUpdate = false;
  const turntable = new THREE.Group();
  turntable.name = "turntable";
  const airframe = new THREE.Group();
  airframe.name = "airframe";
  /** 空中姿态：free 组套在 airframe 外面，负责位移与俯仰、滚转、偏航（绕 DATA.director.pivot 转）；转台照旧绕 z 转。 */
  const free = new THREE.Group();
  free.name = "free";
  free.matrixAutoUpdate = false;
  scene.add(turntable);
  turntable.add(free);
  free.add(airframe);
  // 作品可以把模型整体平移到转台中心（look-dev 只有一段机头时）
  if (DATA.offset) airframe.position.set(...DATA.offset);
  airframe.updateMatrix();
