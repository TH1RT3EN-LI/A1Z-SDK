# A1Z Trash Grasp Asset Set

这套资产是给 A1Z / Isaac 里的桌面垃圾抓取场景准备的第一批 baseline 物体。

当前分两类：

- `raw/poly_pizza/`
  - 可直接脚本下载
  - 适合先把抓取流程跑通
  - 绝大多数是低模材质色，纹理真实感一般
- `manual/`
  - 需要手动从 Sketchfab 等站点下载
  - 贴图通常更完整，更适合后续视觉逼真度提升

另有一版后续更新过的 Isaac YCB 清单：

- `manifest_isaac_ycb.json`
  - 当前 `scripts/place_trash_assets_in_world.py` 默认使用这版
  - 资产直接引用 Isaac Sim 5.1 的 YCB USD
  - 用于当前 world 里的 `TrashSet`
- `manifest.json`
  - 旧的 Poly Pizza baseline
  - 保留作 legacy / 低模直连下载方案

## 目录

- `manifest_isaac_ycb.json`
  - 当前默认 TrashSet 清单
- `manifest.json`
  - 旧版 baseline 清单、来源、许可、推荐尺寸、Isaac 导入备注
- `isaac_asset_candidates.md`
  - 本机已找到的更高质量 Isaac USD 瓶罐候选
- `fetch_poly_pizza_assets.sh`
  - 下载可直连的 `glb`
- `ATTRIBUTION.md`
  - 许可与署名信息

## 快速开始

在仓库根目录执行：

```bash
./assets/trash_grasp_set/fetch_poly_pizza_assets.sh
```

下载后的模型会落到：

```text
assets/trash_grasp_set/raw/poly_pizza/
```

## 本批推荐先用

### 直接可用

1. `can_crushed`
   - 压扁易拉罐
   - 适合测试非规则圆柱抓取
2. `marker_upright`
   - 直立白板笔 / marker
   - 适合测试细长物体的 top-down baseline
3. `bottle_plastic`
   - 塑料瓶
   - 细长、轻质、常见垃圾形态
4. `bottle_water`
   - 另一种细长瓶
   - 可做外形域随机化
5. `paper_debris`
   - 纸类垃圾
   - 更偏场景填充，不是最理想的单体抓取目标

### 手动补强

这三个更适合你后面做“看起来像真实垃圾”的版本：

- `tall_can_of_soda`
  - Sketchfab
  - 2K PBR
- `dirty_plastic_bottle`
  - Sketchfab
  - 2048 贴图，脏污塑料瓶
- `crumbled_paper`
  - Sketchfab
  - 揉皱纸团，带 base color / baked normal

## Isaac 导入建议

### 导入格式

- 优先导入 `glb`
- 导入时打开材质 / materials
- 转成 USD 后单独保存到你自己的 props 目录

### 推荐实物尺寸

如果导入后尺寸不对，按下面 bbox 目标缩放：

- `can_crushed`
  - `0.095 x 0.070 x 0.045 m`
- `marker_upright`
  - `0.028 x 0.028 x 0.150 m`
- `bottle_plastic`
  - `0.070 x 0.070 x 0.220 m`
- `bottle_water`
  - `0.065 x 0.065 x 0.210 m`
- `paper_debris`
  - 如果当散纸垃圾用：
    `0.180 x 0.180 x 0.010 m`
  - 如果只做 clutter，可按场景再缩

### 碰撞体建议

- `can_crushed`
  - `Convex Decomposition`
- `marker_upright`
  - `Convex Hull` 或单圆柱近似
- `bottle_plastic`
  - `Convex Hull`
- `bottle_water`
  - `Convex Hull`
- `paper_debris`
  - 如果参与抓取，用 `Convex Hull`
  - 如果只是场景杂物，可直接简化成薄盒

### 质量建议

- `can_*`
  - `0.012 - 0.020 kg`
- `bottle_*`
  - `0.018 - 0.040 kg`
- `paper_*`
  - `0.003 - 0.010 kg`

## 备注

- 这批里真正“贴图比较像样”的仍然是手动项。
- 直接下载项更像抓取几何 baseline，优点是省事、可复现、许可清楚。
- 如果你下一步要我继续，我可以直接给你补一版：
  - `Isaac props USD` 目标目录规划
  - 一份批量 `glb -> usd` 的导入脚本
  - 一个把这些垃圾随机撒到桌面的场景脚本
