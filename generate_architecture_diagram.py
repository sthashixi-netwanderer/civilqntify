#!/usr/bin/env python3
"""Generate a high-level block diagram of CivilQntify's frontend/backend architecture."""

from mermaid import Mermaid, Graph

MERMAID_SCRIPT = r"""%%{init: {'theme': 'base', 'themeVariables': {'fontSize': '14px', 'primaryColor': '#E8F4FD', 'primaryTextColor': '#1a1a2e', 'primaryBorderColor': '#2196F3', 'lineColor': '#666', 'secondaryColor': '#FFF3E0', 'tertiaryColor': '#E8F5E9'}}}%%

graph TB
    subgraph FRONTEND["FRONTEND — PyQt6 Desktop App"]
        direction TB
        MW["MainWindow<br/>(QTabWidget)"]

        subgraph TABS["Tab Pages"]
            CT["ConcreteMixTab<br/>• Input form<br/>• Info buttons"]
            QT["MaterialQuantifyTab<br/>• Volume/elements input<br/>• Wastage %"]
            CT2["CostEstimationTab<br/>(hidden)"]
        end

        subgraph WORKERS["Background Threads — QThread"]
            MW2["MixDesignWorker<br/>• set_params()<br/>• run()"]
            QW["QuantificationWorker<br/>• set_transfer_data()<br/>• set_volume_mode()"]
        end

        subgraph UI_RESULTS["Result Display"]
            RP["ResultPanel<br/>• Stat cards<br/>• Step-by-step table"]
            QRP["QuantResultPanel<br/>• Material bill table"]
            RPD["ReportPreviewDialog<br/>• PDF preview"]
        end
    end

    subgraph BACKEND["BACKEND — Pure Python Libraries"]
        direction TB

        subgraph CM["concrete_mix package"]
            direction TB
            API["design_mix_simple()<br/>design_mix()"]
            PROP["proportioner.py<br/>• _CODE_REGISTRY dispatch<br/>• design_mix(inp)"]

            subgraph CODES["Code Implementations — Strategy Pattern"]
                IS["IS10262MixDesign<br/>IS 10262:2019"]
                ACI["ACI211MixDesign<br/>ACI 211.1-22"]
            end

            subgraph TABLES["Lookup Tables"]
                IST["is_tables.py<br/>• WATER_CONTENT<br/>• CA_VOLUME_FRACTION<br/>• calculate_target_strength()"]
                ACIT["aci_tables.py<br/>• interpolate_water_content()<br/>• interpolate_w_c_ratio()"]
            end

            subgraph MODELS["Data Models — frozen dataclasses"]
                MDI["MixDesignInput"]
                MDR["MixDesignResult<br/>• CalculationStep trace"]
                MAT["Materials<br/>• Cement, Aggregates<br/>• SCM, Admixture"]
            end

            VCV["volume_calculator.py<br/>absolute_volume()"]
            MOC["moisture_correction.py"]
            VAL["validators.py"]
            EXP["export/<br/>CSV | JSON | PDF | Text"]
            EST["estimators/<br/>cost | carbon"]
            UTL["utils/<br/>units | constants"]
        end

        subgraph MQ["material_quantify package"]
            direction TB
            MQ_API["MaterialQuantifier<br/>• quantify_by_volume()<br/>• quantify_by_elements()"]
            MTD["MixDesignTransferData<br/>• from_mix_design_result()"]
            MB["MaterialBill<br/>• format_report()"]
            SE["StructuralElement<br/>• footing, column<br/>• beam, slab, wall"]
        end
    end

    %% Tab wiring
    MW -->|"tab 1"| CT
    MW -->|"tab 2"| QT
    MW -->|"tab 3 hidden"| CT2

    %% Tabs to Workers
    CT -->|"collect kwargs"| MW2
    QT -->|"set_transfer_data()"| QW

    %% Workers to Backend
    MW2 -->|"design_mix_simple(**kwargs)"| API
    QW -->|"MaterialQuantifier(td)"| MQ_API

    %% Backend internal flow
    API -->|"MixDesignInput →"| PROP
    PROP -->|"dispatch by code"| CODES
    IS -->|"lookup"| IST
    ACI -->|"lookup"| ACIT
    PROP -->|"uses"| VCV
    PROP -->|"adjusts"| MOC
    PROP -->|"validates"| VAL
    PROP -->|"returns"| MDR
    MDI -.->|"frozen input"| PROP
    MAT -.->|"materials"| PROP
    MDR -.->|"result"| EXP
    MDR -.->|"result"| EST
    EXP -.->|"constants"| UTL

    MQ_API -->|"scales per-m3"| MB
    MTD -->|"bridge dataclass"| MQ_API
    SE -->|"element dims"| MQ_API
    MDR -.->|"from result"| MTD

    %% Backend to Frontend results
    MW2 -.->|"result_ready signal"| RP
    QW -.->|"result_ready signal"| QRP
    RP -.->|"export"| EXP
    RP -.->|"preview"| RPD

    %% Cross-tab data handoff signals/slots
    CT -.->|"mix_design_ready signal"| MW
    MW -.->|"load_transfer_data()"| QT
    QRP -.->|"send_to_cost_estimation"| MW
    MW -.->|"load_bill()"| CT2

    %% Styles
    classDef frontend fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1
    classDef worker fill:#FFF3E0,stroke:#E65100,stroke-width:2px,color:#BF360C
    classDef backend fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#1B5E20
    classDef model fill:#F3E5F5,stroke:#6A1B9A,stroke-width:2px,color:#4A148C

    class MW,CT,QT,CT2,RP,QRP,RPD frontend
    class MW2,QW worker
    class API,PROP,IS,ACI,IST,ACIT,VCV,MOC,VAL,EXP,EST,UTL,MQ_API,MTD,MB,SE backend
    class MDI,MDR,MAT model
"""

if __name__ == "__main__":
    graph = Graph("CivilQntify Architecture", MERMAID_SCRIPT)
    graph.save("docs/architecture_block_diagram.mmd")
    print("Saved: docs/architecture_block_diagram.mmd")

    try:
        m = Mermaid(graph, width=1400, height=1000)
        m.save("docs/architecture_block_diagram.svg")
        print("Rendered: docs/architecture_block_diagram.svg")
    except Exception as e:
        print(f"SVG render failed: {e}")
        print("Install mermaid-cli for local rendering: npm install -g @mermaid-js/mermaid-cli")
