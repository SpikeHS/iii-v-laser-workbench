# III–V 激光器科研数据工作台

这是一个**零第三方依赖的轻量框架**，用于把已有分析结果关联到晶圆、样片和器件。
采用 MIT 许可证。Python 3.11 及以上即可运行。

```sh
python workbench.py check examples/project.json
python workbench.py report examples/project.json --out runs/demo.html
```

打开生成的 HTML，查看样品关系、四类分析结果、测量条件和结果文件哈希。
重复生成时使用新的输出文件名。项目清单目前手工编辑。

四类导出适配器均已实现：LIV（analysis.json，schema 0.1.0，仅 CW）、
PL（*_PL_metrics.json，schema 1，保留 Presentation FWHM 语义声明）、
光束（result_summary.json，无顶层版本号，按已知格式检测，全角/半角发散
分别保存，不完整扫描保持可见）、光谱（spectral-analysis.json，schema 0.1.0，
保留 spacing-rule 语义与逐阈值梳齿数；器件/温度需清单补充）。
清单可补填缺失条件；来源文件已记录的值优先，冲突会报错。
重复引用同一结果文件会被拒绝。

三个来源工具均已在组内使用：PL-Analyzer 完整公开应用源码；laser-beam-qa 和
laser-characterization-tools 公开的是去除研究专用预设和实验 setup 后的通用内容。
本工作台是新建原型，现阶段提供手工关联和结果查看。

**示例中四份结果均为合成数据，但都由真实工具生成**：PL 指标 JSON 来自
PL-Analyzer 的展示导出器，光束摘要来自 lbqa-simulated-zscan 命令行，
光谱导出来自查看器自身的分析函数，LIV 导出来自 laser-liv 命令行。
当前检查 ID、关系、文件、格式与条件；尚未实现科学单位与条件一致性
检查、联合计算、仪器采集或预测模型。

下一步将实现正式输出适配和可复现的跨工具案例，详见[路线图](ROADMAP.md)。
通用框架与实验室具体配置分开维护；本仓库不含实验数据、研究专用配置。
