# 终末地产线计算器
明日方舟终末地基建产线计算器，根据产线数量自行计算所需材料入口通道数，并可在限制下计算出各地区最高出售价格的规划方案

<img width="1000" height="500" alt="软件界面" src="https://github.com/user-attachments/assets/f2af3e1e-ede1-436b-9236-9c2d5f2444be" />

## 限制设置

可分别对地区和具体数值进行限制

<img width="337" height="340" alt="限制设置" src="https://github.com/user-attachments/assets/3b4111c0-ed2c-4bc7-8c7b-d2fab936596b" />

>[!NOTE]
>此处的限制为取货通道数量限制，即游戏内显示 **数量 / 30** 计算，可输入分数。
>
>超库存传输原材料时，需要将 **传输材料 / 1800** 计算。
>
>当区域被选择后，输入的产线数量会自行阻止消耗数量超出限制

## 产线选择

可自行添加需求的产线数量，并在当前已有内容的基础上进行最高的出售金额方案计算

<img width="400" height="500" alt="优化方案" src="https://github.com/user-attachments/assets/2512e41e-7e60-4e59-a25a-d95cc2a2e52f" />

对于制作时间为**2秒**的产品，计数与游戏内相同

制作时间为**10秒**的产品，则变为1/5输入消耗与1/5出售价格，从而得到正确数据

## 计算结果

在输入产线后，将分别计算 **基础材料消耗** **设备需求** **电力需求** **占地面积需求**

<img width="600" height="400" alt="12d1930991cd04293e2d91d26c0b6d4e" src="https://github.com/user-attachments/assets/e492409f-eb99-4d84-b296-6041e476d82c" />

<img width="600" height="460" alt="289e6ccb52a38178bf2410c10180469c" src="https://github.com/user-attachments/assets/96036ff9-c549-4ab6-9982-1ad126c27c33" />

<img width="600" height="400" alt="01599a8ebffc28c8c60ad1790fb760d6" src="https://github.com/user-attachments/assets/83c947e0-e540-43fc-a8d9-91b378c26eef" />

其中占地面积为理想状态，除了设备本身占用，每个输入与输出的道路只占1个格子。不整合情况下，还会计算每个设备入口处，除输入产品的道路外，剩余所有可能的无法利用的道路。

## 流程显示

输入产线后，右侧画布还会同时显示所有产线的流程图，可进行拖动与放大缩小。

在流程图中会完整的显示数量

右上角还有仅显示流程按钮，点击后窗口将固定在右上角，方便建造

<img width="500" height="550" alt="d6cd1eec490493212348077ca360a488" src="https://github.com/user-attachments/assets/8bd35c45-3175-4fd5-a211-f366c5407d4a" />

>[!NOTE]
>由于可使用分流器与汇流器，得到1/2 1/3等数量产线，因此在程序设计时，使用最低单位为1/36
>

## 自主更新factory_db.xlsx

如需自行更新数据，请查看以下说明

所有数据全部存储在表格内，仅需更新表格即可更新数据。

### Items表

<img width="500" height="360" alt="c9492fb58126a816da069bb49e85c877" src="https://github.com/user-attachments/assets/9af78dc6-b4f1-47bd-9145-c38c1e72352f" />

materials列中记录了所有制作相关的材料与产品，后续版本更新时，**必须**先在此处进行添加，表格中其他输入材料产品部分使用此列作为检测源。其中带有(植物)的材料为同名植物的占位符，由于通过正常1采种2种植或是水培时1种植1采种即可无限植物，为了避免该产业链无限递归，此处使用该占位符用来计算实际电量消耗与空间消耗。

Select_tool列记录所有工业设备，其中植物培养与植物培养(水培)为植物的培养方案

size为设备占地大小

Nsize为每个设备除了输入外通常浪费的格数

ele为每个设备消耗电力

### Limit表

<img width="365" height="172" alt="4fc99922730071c14d42bf0973716b37" src="https://github.com/user-attachments/assets/9eb608d1-601d-4cc0-b710-6e71bcbafe8b" />

其中记录了各个地区目前的 最高限制/30 (设备除外) ，空白为无限制，0为禁止

### Recipes配方表

其中记录所有配方

<img width="600" height="70" alt="9a49e6f294de6a4103b7c3bb42b9be32" src="https://github.com/user-attachments/assets/135cb11a-2426-4f3d-9fe8-fbbb08ada379" />

output为输出产品

output_qty为该公式输出产品数量，默认公式为2s反应一次，若公式默认为10s/次，则仍填写1，但后续inputs所有输入/5

inputs为输入 格式为 材料1:数量;材料2:数量... 若10秒/次，则按照1/5记录

tool为反应设备

识别种类与错误位置为inputs的检测，当inputs输入有错误时，将会自动进行检测，如果显示全部正确，则没有问题，若显示材料:数量，则该材料填写有问题，若为空，则;数量有问题

>[!WARNING]
>在所有的公式中，不应该出现直接的种植与采种，或是拆解机，
>应当以荞花	1	(荞花):1	植物培养 使用占位符与组合植物培养进行记录

### 商品记录表

以sell_地区名称命名表格，其中内容为商品名称 价格

其中价格为每两秒单产线产生价值，因此10秒产线也要对 **价格 / 5** 计算 

<img width="245" height="175" alt="b662535668bba010cb7485b008abb1b6" src="https://github.com/user-attachments/assets/aaade00e-ac6c-460b-be71-7eead13c53b4" />

>[!NOTE]
>其中若存在大量需求且不可能真卖出的产物，如息壤，则应该将价格调为0或删除该行


# 该程序为免费分享 由B站Dumz_制作
（虽然我没有发过zmd的视频，因为几天肝完了开始收菜长草该去玩别的游戏了，视频就懒得做了）
