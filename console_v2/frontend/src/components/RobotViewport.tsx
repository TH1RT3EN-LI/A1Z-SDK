import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import URDFLoader from "urdf-loader";

type ModelStatus = "loading" | "ready" | "error";

function fitCameraToObject(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  object: THREE.Object3D,
) {
  object.updateMatrixWorld(true);
  const bounds = new THREE.Box3().setFromObject(object);
  const size = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  const maximumDimension = Math.max(size.x, size.y, size.z);
  const direction = new THREE.Vector3(1.25, 0.8, 1.3).normalize();

  camera.near = Math.max(maximumDimension / 100, 0.001);
  camera.far = Math.max(maximumDimension * 100, 10);
  camera.position.copy(center).add(direction.multiplyScalar(maximumDimension * 2.15));
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

export default function RobotViewport() {
  const hostRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<ModelStatus>("loading");

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#0b0f15");
    scene.fog = new THREE.Fog("#0b0f15", 2.4, 5.5);

    const camera = new THREE.PerspectiveCamera(36, 1, 0.005, 100);
    camera.position.set(1.2, 0.9, 1.2);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    host.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.075;
    controls.screenSpacePanning = true;
    controls.minDistance = 0.25;
    controls.maxDistance = 4;

    scene.add(new THREE.HemisphereLight("#d9efff", "#17202a", 2.4));
    const keyLight = new THREE.DirectionalLight("#ffffff", 3.2);
    keyLight.position.set(1.5, 2.4, 1.8);
    keyLight.castShadow = true;
    scene.add(keyLight);
    const rimLight = new THREE.DirectionalLight("#55bde9", 1.8);
    rimLight.position.set(-1.8, 1.1, -1.4);
    scene.add(rimLight);

    const grid = new THREE.GridHelper(2.4, 24, "#334353", "#1b2530");
    grid.material.transparent = true;
    grid.material.opacity = 0.65;
    scene.add(grid);

    const loadingManager = new THREE.LoadingManager();
    const loader = new URDFLoader(loadingManager);
    const modelRoot = new URL("model/A1Z_G1Z/", document.baseURI).href;
    loader.packages = { A1Z_G1Z: modelRoot };
    let robot: THREE.Object3D | undefined;

    loadingManager.onLoad = () => {
      if (!robot) return;
      fitCameraToObject(camera, controls, robot);
      setStatus("ready");
    };

    loadingManager.onError = (url) => {
      console.error("Unable to load an A1Z model asset", url);
      setStatus("error");
    };

    loader.load(
      new URL("urdf/A1Z_G1Z_control.urdf", modelRoot).href,
      (loadedRobot) => {
        robot = loadedRobot;
        loadedRobot.rotation.x = -Math.PI / 2;
        loadedRobot.setJointValue("arm_joint1", 0.15);
        loadedRobot.setJointValue("arm_joint2", 1.05);
        loadedRobot.setJointValue("arm_joint3", -1.65);
        loadedRobot.setJointValue("arm_joint4", 0.1);
        loadedRobot.setJointValue("arm_joint5", 0.55);
        loadedRobot.setJointValue("arm_joint6", 0);
        loadedRobot.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.castShadow = true;
            child.receiveShadow = true;
          }
        });
        scene.add(loadedRobot);
      },
      undefined,
      (error) => {
        console.error("Unable to load the A1Z model", error);
        setStatus("error");
      },
    );

    const resize = () => {
      const width = Math.max(host.clientWidth, 1);
      const height = Math.max(host.clientHeight, 1);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(host);
    resize();

    let animationFrame = 0;
    const render = () => {
      controls.update();
      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(render);
    };
    render();

    return () => {
      window.cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      controls.dispose();
      if (robot) {
        robot.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.geometry.dispose();
            const materials = Array.isArray(child.material) ? child.material : [child.material];
            materials.forEach((material) => material.dispose());
          }
        });
      }
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return (
    <div className="robot-viewport" ref={hostRef}>
      <div className={`model-state is-${status}`}>
        <span />
        {status === "loading" && "加载完整模型"}
        {status === "ready" && "静态模型 · 未接遥测"}
        {status === "error" && "模型加载失败"}
      </div>
      <div className="viewport-help">左键旋转 · 滚轮缩放 · 右键平移</div>
    </div>
  );
}
