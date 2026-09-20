# III–V 激光器科研数据工作台

这是一个**零第三方依赖的轻量框架**，用于把已有分析结果关联到晶圆、样片和器件。
维护者为 Sen Hu（SpikeHS），采用 MIT 许可证。Python 3.11 及以上即可运行。

```sh
python workbench.py check examples/project.json
python workbench.py report examples/project.json --out runs/demo.html
```

打开生成的 HTML，查看样品关系、四类分析结果、测量条件和结果文件哈希。
重复生成时使用新的输出文件名。项目清单目前手工编辑。

已实现 LIV 导出适配器：解析 laser-characterization-tools 的 `analysis.json`
（schema 0.1.0，仅 CW），保留线性外推方法标记、拟合区间、阈值、斜率、
最大功率、原始输入溯源和警告。清单可补填缺失条件（如温度）；来源文件
已记录的值优先，冲突会报错。重复引用同一结果文件会被拒绝。
其余三类结果目前原样显示来源 JSON，专用适配器见路线图。

三个来源工具均已在组内使用：PL-Analyzer 完整公开应用源码；laser-beam-qa 和
laser-characterization-tools 公开的是去除研究专用预设和实验 setup 后的通用内容。
本工作台是新建原型，现阶段提供手工关联和结果查看。

**示例中 PL、光束、光谱三份 JSON 是手工编写的合成占位结果；LIV 结果由
`laser-liv` 命令行对合成曲线实际运行生成，均不是实测数据。**
当前检查 ID、关系、文件和基本结构，显示来源 JSON；尚未实现其余工具的
专用格式适配、科学单位与条件一致性检查、联合计算、仪器采集或预测模型。

下一步将实现正式输出适配和可复现的跨工具案例，详见[路线图](ROADMAP.md)。
通用框架与实验室具体配置分开维护；本仓库不含实验数据、机构名称或研究专用配置。
