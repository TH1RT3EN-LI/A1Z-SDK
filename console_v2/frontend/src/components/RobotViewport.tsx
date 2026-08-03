import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import URDFLoader, { type URDFRobot } from "urdf-loader";
import { viewportThemes, type ThemeMode } from "../theme";

type ModelStatus = "loading" | "ready" | "error";
type RobotViewportPresentation = "workspace" | "ambient";
type AmbientPreviewVariant = 0 | 1 | 2;
type AmbientPreviewController = {
  transitionTo: (variant: AmbientPreviewVariant, immediate?: boolean) => void;
};
type AmbientCameraAnchor = {
  direction: THREE.Vector3;
  sceneScale: number;
  up: THREE.Vector3;
};

const ambientPreviewPoses = [
  [0.12, 1.02, -1.62, 0.08, 0.58, 0],
  [1, 0.25, -2.55, -1.15, 1.25, -1.55],
  [-0.8, 2.55, -2.85, 1.2, -0.95, 1.65],
] as const;

const ambientViewDirection = new THREE.Vector3(1.3, 0.35, 1.25);
const ambientPreviewDistances = [2.6, 1.25, 1.5] as const;

function fitCameraToObject(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  object: THREE.Object3D,
  distanceFactor = 2.15,
  viewDirection = new THREE.Vector3(1.25, 0.8, 1.3),
) {
  object.updateMatrixWorld(true);
  const bounds = new THREE.Box3().setFromObject(object);
  if (bounds.isEmpty()) return null;
  const size = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  const maximumDimension = Math.max(size.x, size.y, size.z);
  if (!Number.isFinite(maximumDimension) || maximumDimension <= 0.001) return null;
  const direction = viewDirection.clone().normalize();

  camera.near = Math.max(maximumDimension / 100, 0.001);
  camera.far = Math.max(maximumDimension * 100, 10);
  camera.position.copy(center).add(direction.multiplyScalar(maximumDimension * distanceFactor));
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
  return [...center.toArray(), ...size.toArray()].map((value) => value.toFixed(4)).join(":");
}

function getBoundsSignature(object: THREE.Object3D) {
  object.updateMatrixWorld(true);
  const bounds = new THREE.Box3().setFromObject(object);
  if (bounds.isEmpty()) return null;
  const size = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  if (![...center.toArray(), ...size.toArray()].every(Number.isFinite)) return null;
  return [...center.toArray(), ...size.toArray()].map((value) => value.toFixed(4)).join(":");
}

function disposeRobot(root: THREE.Object3D) {
  root.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      child.geometry.dispose();
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      materials.forEach((material) => material.dispose());
    }
  });
}

export default function RobotViewport({
  theme,
  presentation = "workspace",
  previewVariant = 0,
  jointPositionsDeg = null,
  showJointLabels = false,
}: {
  theme: ThemeMode;
  presentation?: RobotViewportPresentation;
  previewVariant?: AmbientPreviewVariant;
  jointPositionsDeg?: readonly number[] | null;
  showJointLabels?: boolean;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const jointLabelRefs = useRef<Array<HTMLOutputElement | null>>([]);
  const jointLeaderSvgRef = useRef<SVGSVGElement>(null);
  const jointLeaderPathRefs = useRef<Array<SVGPathElement | null>>([]);
  const jointAnchorRefs = useRef<Array<SVGCircleElement | null>>([]);
  const previewControllerRef = useRef<AmbientPreviewController | null>(null);
  const previewVariantRef = useRef(previewVariant);
  const jointPositionsRef = useRef<readonly number[] | null>(jointPositionsDeg);
  const showJointLabelsRef = useRef(showJointLabels);
  const [status, setStatus] = useState<ModelStatus>("loading");
  previewVariantRef.current = previewVariant;
  jointPositionsRef.current = jointPositionsDeg;
  showJointLabelsRef.current = showJointLabels;

  useEffect(() => {
    if (presentation === "ambient") {
      previewControllerRef.current?.transitionTo(previewVariant);
    }
  }, [presentation, previewVariant]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;
    const palette = viewportThemes[theme];
    const ambient = presentation === "ambient";
    let disposed = false;
    setStatus("loading");

    const scene = new THREE.Scene();
    if (!ambient) {
      scene.background = new THREE.Color(palette.background);
      scene.fog = new THREE.Fog(palette.fog, 2.4, 5.5);
    }

    const camera = new THREE.PerspectiveCamera(36, 1, 0.005, 100);
    camera.position.set(1.2, 0.9, 1.2);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: ambient });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = ambient ? THREE.ACESFilmicToneMapping : THREE.NoToneMapping;
    renderer.toneMappingExposure = ambient ? 1.12 : 1;
    renderer.shadowMap.enabled = !ambient;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    if (ambient) renderer.setClearColor(0x000000, 0);
    host.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.075;
    controls.enabled = !ambient;
    controls.screenSpacePanning = true;
    controls.minDistance = 0.25;
    controls.maxDistance = 4;

    scene.add(
      new THREE.HemisphereLight(
        palette.hemisphereSky,
        palette.hemisphereGround,
        ambient ? (theme === "light" ? 1.6 : 1.9) : theme === "light" ? 2 : 2.4,
      ),
    );
    const keyLight = new THREE.DirectionalLight(
      palette.keyLight,
      ambient ? (theme === "light" ? 3 : 4.2) : theme === "light" ? 2.6 : 3.2,
    );
    keyLight.position.set(ambient ? 2.4 : 1.5, ambient ? 1.7 : 2.4, ambient ? 2.1 : 1.8);
    keyLight.castShadow = true;
    scene.add(keyLight);
    const rimLight = new THREE.DirectionalLight(
      palette.rimLight,
      ambient ? (theme === "light" ? 1.5 : 3.2) : theme === "light" ? 1.1 : 1.8,
    );
    rimLight.position.set(ambient ? -2.6 : -1.8, ambient ? 0.8 : 1.1, ambient ? -2.3 : -1.4);
    scene.add(rimLight);

    if (!ambient) {
      const grid = new THREE.GridHelper(2.4, 24, palette.gridMajor, palette.gridMinor);
      grid.material.transparent = true;
      grid.material.opacity = 0.65;
      scene.add(grid);
    }

    const loadingManager = new THREE.LoadingManager();
    const loader = new URDFLoader(loadingManager);
    const modelRoot = new URL("model/A1Z_G1Z/", document.baseURI).href;
    loader.packages = { A1Z_G1Z: modelRoot };
    let robot: URDFRobot | undefined;
    let cameraFitFrame = 0;
    let previewMotionFrame = 0;
    let previewSettleTimer = 0;
    let previewSettling = false;
    let previewSettleStartedAt = 0;
    let previewLastProgressAt = 0;
    let lastBoundsSignature = "";
    let stableBoundsFrames = 0;
    let ambientCameraAnchor: AmbientCameraAnchor | null = null;
    let currentPose: number[] = [...ambientPreviewPoses[previewVariantRef.current]];
    let currentPreviewDistance = ambientPreviewDistances[previewVariantRef.current];
    let lastWorkspacePose: number[] | null = null;
    const projectedPosition = new THREE.Vector3();

    const getToolFrame = () => robot?.links.grasp_tcp;

    const captureAmbientCameraAnchor = () => {
      const toolFrame = getToolFrame();
      if (!ambient || !robot || !toolFrame || ambientCameraAnchor) return;
      robot.updateMatrixWorld(true);
      const size = new THREE.Box3().setFromObject(robot).getSize(new THREE.Vector3());
      const maximumDimension = Math.max(size.x, size.y, size.z);
      ambientCameraAnchor = {
        direction: ambientViewDirection.clone().normalize(),
        sceneScale: maximumDimension,
        up: new THREE.Vector3(0, 1, 0),
      };
      applyAmbientCameraAnchor();
    };

    const applyAmbientCameraAnchor = () => {
      const toolFrame = getToolFrame();
      if (!ambientCameraAnchor || !robot || !toolFrame) return false;
      robot.updateMatrixWorld(true);
      const toolPosition = toolFrame.getWorldPosition(new THREE.Vector3());
      camera.position
        .copy(toolPosition)
        .addScaledVector(
          ambientCameraAnchor.direction,
          ambientCameraAnchor.sceneScale * currentPreviewDistance,
        );
      camera.up.copy(ambientCameraAnchor.up);
      controls.target.copy(toolPosition);
      controls.update();
      return true;
    };

    const fitRobot = () => {
      if (disposed || !robot) return null;
      if (ambient && applyAmbientCameraAnchor()) return getBoundsSignature(robot);
      return fitCameraToObject(
        camera,
        controls,
        robot,
        ambient ? currentPreviewDistance : 2.15,
        ambient ? ambientViewDirection : undefined,
      );
    };

    const applyPreviewPose = () => {
      if (!robot) return;
      currentPose.forEach((value, index) => robot?.setJointValue(`arm_joint${index + 1}`, value));
      fitRobot();
    };

    const applyMeasuredWorkspacePose = () => {
      if (ambient || !robot) return;
      const measured = jointPositionsRef.current;
      if (
        !measured ||
        measured.length < 6 ||
        !measured.slice(0, 6).every(Number.isFinite)
      ) {
        return;
      }
      const pose = measured.slice(0, 6).map((value) => THREE.MathUtils.degToRad(value));
      if (
        lastWorkspacePose &&
        pose.every((value, index) => Math.abs(value - lastWorkspacePose![index]) < 1e-6)
      ) {
        return;
      }
      pose.forEach((value, index) => robot?.setJointValue(`arm_joint${index + 1}`, value));
      lastWorkspacePose = pose;
    };

    const updateJointLabels = () => {
      if (ambient || !robot || !showJointLabelsRef.current) return;
      robot.updateMatrixWorld(true);
      const width = Math.max(host.clientWidth, 1);
      const height = Math.max(host.clientHeight, 1);
      jointLeaderSvgRef.current?.setAttribute("viewBox", `0 0 ${width} ${height}`);

      const annotations: Array<{
        anchor: SVGCircleElement;
        anchorX: number;
        anchorY: number;
        label: HTMLOutputElement;
        path: SVGPathElement;
        side: "left" | "right";
      }> = [];

      jointLabelRefs.current.forEach((label, index) => {
        const joint = robot?.joints[`arm_joint${index + 1}`];
        const path = jointLeaderPathRefs.current[index];
        const anchor = jointAnchorRefs.current[index];
        if (!label || !path || !anchor || !joint) return;
        joint.getWorldPosition(projectedPosition).project(camera);
        const visible =
          projectedPosition.z >= -1 &&
          projectedPosition.z <= 1 &&
          Math.abs(projectedPosition.x) <= 1.15 &&
          Math.abs(projectedPosition.y) <= 1.15;
        if (!visible) {
          label.style.opacity = "0";
          path.style.opacity = "0";
          anchor.style.opacity = "0";
          return;
        }
        annotations.push({
          anchor,
          anchorX: (projectedPosition.x * 0.5 + 0.5) * width,
          anchorY: (-projectedPosition.y * 0.5 + 0.5) * height,
          label,
          path,
          side: index === 0 || index === 1 || index === 3 ? "left" : "right",
        });
      });

      const layoutSide = (
        items: typeof annotations,
        side: "left" | "right",
      ) => {
        const edgeInset = 12;
        const verticalInset = 12;
        const minimumGap = 7;
        const sorted = items
          .filter((item) => item.side === side)
          .sort((a, b) => a.anchorY - b.anchorY);
        const measurements = sorted.map((item) => ({
          height: Math.max(item.label.offsetHeight, 24),
          width: Math.max(item.label.offsetWidth, 68),
        }));
        const tops = sorted.map((item, index) =>
          THREE.MathUtils.clamp(
            item.anchorY - measurements[index].height / 2,
            verticalInset,
            height - verticalInset - measurements[index].height,
          ),
        );

        for (let index = 1; index < tops.length; index += 1) {
          tops[index] = Math.max(
            tops[index],
            tops[index - 1] + measurements[index - 1].height + minimumGap,
          );
        }
        if (tops.length > 0) {
          const last = tops.length - 1;
          const overflow =
            tops[last] + measurements[last].height - (height - verticalInset);
          if (overflow > 0) tops.forEach((_, index) => { tops[index] -= overflow; });
          for (let index = tops.length - 2; index >= 0; index -= 1) {
            tops[index] = Math.min(
              tops[index],
              tops[index + 1] - measurements[index].height - minimumGap,
            );
          }
          const underflow = verticalInset - tops[0];
          if (underflow > 0) tops.forEach((_, index) => { tops[index] += underflow; });
        }

        sorted.forEach((item, index) => {
          const labelWidth = measurements[index].width;
          const labelHeight = measurements[index].height;
          const labelLeft = side === "left"
            ? edgeInset
            : width - edgeInset - labelWidth;
          const labelCenterY = tops[index] + labelHeight / 2;
          const endpointX = side === "left" ? labelLeft + labelWidth : labelLeft;
          const kneeX = endpointX + (item.anchorX - endpointX) * 0.52;

          item.label.dataset.side = side;
          item.label.style.left = `${labelLeft}px`;
          item.label.style.top = `${tops[index]}px`;
          item.label.style.opacity = "1";
          item.path.setAttribute(
            "d",
            `M ${item.anchorX.toFixed(2)} ${item.anchorY.toFixed(2)} ` +
              `H ${kneeX.toFixed(2)} V ${labelCenterY.toFixed(2)} H ${endpointX.toFixed(2)}`,
          );
          item.path.style.opacity = "1";
          item.anchor.setAttribute("cx", item.anchorX.toFixed(2));
          item.anchor.setAttribute("cy", item.anchorY.toFixed(2));
          item.anchor.style.opacity = "1";
        });
      };

      layoutSide(annotations, "left");
      layoutSide(annotations, "right");
    };

    const transitionPreview = (variant: AmbientPreviewVariant, immediate = false) => {
      if (!ambient || !robot) return;
      window.cancelAnimationFrame(previewMotionFrame);
      const targetPose = ambientPreviewPoses[variant];
      const targetPreviewDistance = ambientPreviewDistances[variant];
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      if (immediate || reducedMotion) {
        currentPose = [...targetPose];
        currentPreviewDistance = targetPreviewDistance;
        applyPreviewPose();
        return;
      }

      const sourcePose = [...currentPose];
      const sourcePreviewDistance = currentPreviewDistance;
      const startedAt = performance.now();
      const duration = 1200;

      const animate = (now: number) => {
        if (disposed) return;
        const progress = Math.min((now - startedAt) / duration, 1);
        const eased =
          progress * progress * progress * (progress * (progress * 6 - 15) + 10);
        currentPose = sourcePose.map(
          (value, index) => value + (targetPose[index] - value) * eased,
        );
        currentPreviewDistance =
          sourcePreviewDistance + (targetPreviewDistance - sourcePreviewDistance) * eased;
        applyPreviewPose();
        if (progress < 1) previewMotionFrame = window.requestAnimationFrame(animate);
      };

      previewMotionFrame = window.requestAnimationFrame(animate);
    };

    const previewController: AmbientPreviewController = { transitionTo: transitionPreview };
    previewControllerRef.current = previewController;

    const scheduleCameraFit = () => {
      window.cancelAnimationFrame(cameraFitFrame);
      cameraFitFrame = window.requestAnimationFrame(fitRobot);
    };

    const settleAmbientPreview = () => {
      if (disposed) return;
      const now = performance.now();
      const boundsSignature = fitRobot();
      if (boundsSignature && boundsSignature === lastBoundsSignature) stableBoundsFrames += 1;
      else stableBoundsFrames = 0;
      lastBoundsSignature = boundsSignature ?? "";

      const elapsed = now - previewSettleStartedAt;
      const quietFor = now - previewLastProgressAt;
      if (
        boundsSignature &&
        stableBoundsFrames >= 6 &&
        elapsed >= 260 &&
        quietFor >= 180
      ) {
        captureAmbientCameraAnchor();
        previewSettling = false;
        setStatus("ready");
        return;
      }
      if (elapsed >= 1800) {
        if (boundsSignature) captureAmbientCameraAnchor();
        previewSettling = false;
        setStatus(boundsSignature ? "ready" : "error");
        return;
      }
      previewSettleTimer = window.setTimeout(settleAmbientPreview, 50);
    };

    const beginAmbientPreviewSettlement = () => {
      if (!ambient || disposed || !robot || previewSettling) return;
      previewSettling = true;
      previewSettleStartedAt = performance.now();
      previewLastProgressAt = previewSettleStartedAt;
      lastBoundsSignature = "";
      stableBoundsFrames = 0;
      previewSettleTimer = window.setTimeout(settleAmbientPreview, 50);
    };

    loadingManager.onLoad = () => {
      if (disposed || !robot) return;
      if (ambient) {
        previewLastProgressAt = performance.now();
        beginAmbientPreviewSettlement();
      }
      else {
        scheduleCameraFit();
        setStatus("ready");
      }
    };

    loadingManager.onProgress = () => {
      previewLastProgressAt = performance.now();
      scheduleCameraFit();
      beginAmbientPreviewSettlement();
    };

    loadingManager.onError = (url) => {
      if (disposed) return;
      console.error("Unable to load an A1Z model asset", url);
      if (!ambient) setStatus("error");
    };

    loader.load(
      new URL("urdf/A1Z_G1Z_control.urdf", modelRoot).href,
      (loadedRobot) => {
        if (disposed) {
          disposeRobot(loadedRobot);
          return;
        }
        robot = loadedRobot;
        loadedRobot.rotation.x = -Math.PI / 2;
        const initialVariant = ambient ? previewVariantRef.current : 0;
        currentPose = [...ambientPreviewPoses[initialVariant]];
        currentPreviewDistance = ambientPreviewDistances[initialVariant];
        currentPose.forEach((value, index) =>
          loadedRobot.setJointValue(`arm_joint${index + 1}`, value),
        );
        applyMeasuredWorkspacePose();
        loadedRobot.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.castShadow = true;
            child.receiveShadow = true;
          }
        });
        scene.add(loadedRobot);
        scheduleCameraFit();
        beginAmbientPreviewSettlement();
      },
      undefined,
      (error) => {
        if (disposed) return;
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
      applyMeasuredWorkspacePose();
      controls.update();
      updateJointLabels();
      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(render);
    };
    render();

    return () => {
      disposed = true;
      window.cancelAnimationFrame(animationFrame);
      window.cancelAnimationFrame(cameraFitFrame);
      window.cancelAnimationFrame(previewMotionFrame);
      window.clearTimeout(previewSettleTimer);
      if (previewControllerRef.current === previewController) previewControllerRef.current = null;
      resizeObserver.disconnect();
      controls.dispose();
      if (robot) disposeRobot(robot);
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [presentation, theme]);

  return (
    <div
      className={`robot-viewport is-${status} ${presentation === "ambient" ? "is-ambient" : ""}`}
      ref={hostRef}
    >
      {presentation === "workspace" ? (
        <div
          className={`joint-label-layer ${showJointLabels ? "is-visible" : ""}`}
          aria-hidden={!showJointLabels}
        >
          <svg
            className="joint-leader-layer"
            ref={jointLeaderSvgRef}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            {Array.from({ length: 6 }, (_, index) => (
              <path
                className="joint-leader-path"
                key={`path-${index}`}
                ref={(element) => {
                  jointLeaderPathRefs.current[index] = element;
                }}
              />
            ))}
            {Array.from({ length: 6 }, (_, index) => (
              <circle
                className="joint-leader-anchor"
                key={`anchor-${index}`}
                r="2.25"
                ref={(element) => {
                  jointAnchorRefs.current[index] = element;
                }}
              />
            ))}
          </svg>
          {Array.from({ length: 6 }, (_, index) => {
            const value = jointPositionsDeg?.[index];
            return (
              <output
                className="joint-model-label"
                data-joint={`J${index + 1}`}
                key={index}
                ref={(element) => {
                  jointLabelRefs.current[index] = element;
                }}
              >
                {Number.isFinite(value) ? `${Number(value).toFixed(1)}°` : "—"}
              </output>
            );
          })}
        </div>
      ) : null}
      {status === "error" && presentation === "workspace" ? (
        <div className="model-state is-error" role="alert">
          <span />
          模型加载失败
        </div>
      ) : null}
    </div>
  );
}
