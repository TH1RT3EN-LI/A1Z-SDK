# Isaac Asset Candidates For Better Bottles And Cans

当前仓库里在用的瓶瓶罐罐来自 Poly Pizza，位置见：

- [manifest.json](/home/th1rt3en/dev/forge/A1Z/assets/trash_grasp_set/manifest.json)
- [place_trash_assets_in_world.py](/home/th1rt3en/dev/forge/A1Z/scripts/place_trash_assets_in_world.py)

这批资产适合先把流程跑通，但模型质量偏低。

## 本机检查结果

- `~/isaacasset`
  - 不存在
- 实际找到的 Isaac 资产目录：
  - `/home/th1rt3en/isaacsim_assets`

## 首选候选

这几项最适合直接替代当前低模瓶罐：

1. `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Props/YCB/Axis_Aligned/002_master_chef_can.usd`
2. `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Props/YCB/Axis_Aligned/005_tomato_soup_can.usd`
3. `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Props/YCB/Axis_Aligned/006_mustard_bottle.usd`
4. `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Props/YCB/Axis_Aligned/007_tuna_fish_can.usd`

说明：

- 这是 YCB 标准物体，抓取基准价值更高。
- 文件体量大约 `452K - 616K`，明显比当前那批更像完整资产。
- 如果想优先要带物理配置的版本，还能用：
  - `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Props/YCB/Axis_Aligned_Physics/005_tomato_soup_can.usd`
  - `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Props/YCB/Axis_Aligned_Physics/006_mustard_bottle.usd`

## 次优候选

这些更像场景道具，外观通常也比 Poly Pizza 好，但更偏环境 props：

- `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Environments/Simple_Warehouse/Props/SM_BottlePlasticA_01.usd`
- `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Environments/Simple_Warehouse/Props/SM_BottlePlasticB_01.usd`
- `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Environments/Simple_Warehouse/Props/SM_BottlePlasticE_01.usd`
- `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Environments/Office/Props/SM_BottleA.usd`
- `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Environments/Office/Props/SM_BottleB.usd`
- `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Environments/Hospital/Props/SM_BottleA.usd`
- `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Environments/Hospital/Props/SM_BottleB.usd`
- `/home/th1rt3en/isaacsim_assets/Assets/Isaac/6.0/Isaac/Environments/Hospital/Props/SM_PillBottle_01v.usd`

说明：

- 这些 USD 文件本身更小，像是场景资产装配件。
- 其中 `SM_BottlePlasticA_01.usd` 约 `20K`，`SM_PillBottle_01v.usd` 约 `12K`。
- 能不能直接当抓取目标用，还要看你是要“场景观感”还是“抓取基准”。

## 结论

如果你的目标是替掉当前低质量瓶罐，优先顺序建议是：

1. `002_master_chef_can`
2. `005_tomato_soup_can`
3. `006_mustard_bottle`
4. `007_tuna_fish_can`

如果目标是“看起来像真实场景里的瓶子”，再考虑：

1. `SM_BottlePlasticA_01`
2. `SM_BottlePlasticE_01`
3. `SM_PillBottle_01v`

## 当前约束

当前 [place_trash_assets_in_world.py](/home/th1rt3en/dev/forge/A1Z/scripts/place_trash_assets_in_world.py) 只支持：

- 从 `assets/trash_grasp_set/raw/poly_pizza/*.glb` 读取
- 用 `trimesh` bake 进 world USD

它现在不支持直接引用这些现成的 Isaac USD 资产。

所以“有更好的资产”已经确认；下一步如果要真正替换场景，需要：

1. 改脚本支持 `usd reference`
2. 或者单独写一个直接把这些 USD 挂进 world 的脚本
