"""Plano de experimentação"""
from pathlib import Path
import matplotlib.pyplot as plt
import mlflow
from mlflow.tracking import MlflowClient
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, silhouette_score
from modelo import CENARIOS, SEMENTE, agrupar, escalar, hiperparametros, soma_quadrados_intra

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = Path("dados") / "saidas"
EXPERIMENTO = "tipologia_municipios_para"
ALGORITMOS = ["kmeans", "ward", "kmedoids"]
VALORES_K = list(range(2, 9))
N_SUBAMOSTRAS = 100
FRACAO_SUBAMOSTRA = 0.8
METRICAS = {"silhueta": "Silhueta (144 municípios)",
            "soma_quadrados_intra": "Soma de quadrados intragrupo",
            "silhueta_media_subamostras": "Silhueta média (subamostras)",
            "ari_estabilidade_medio": "ARI de estabilidade médio"}

matriz = pd.read_csv(SAIDA / "matriz_modelo.csv", index_col="cod_mun")
print(f"Matriz do modelo: {matriz.shape[0]} municípios x {matriz.shape[1]} variáveis")
municipios = matriz.index

gerador = np.random.default_rng(SEMENTE)
tamanho = int(FRACAO_SUBAMOSTRA * len(municipios))
subamostras = []
for b in range(N_SUBAMOSTRAS):
    subamostras.append(np.sort(gerador.choice(municipios, size=tamanho, replace=False)))

resultados = []
for cenario, configuracao in CENARIOS.items():
    Z = escalar(matriz, configuracao["padronizacao"])
    for algoritmo in ALGORITMOS:
        for k in VALORES_K:
            grupos = agrupar(Z, algoritmo, k)
            silhuetas_sub = []
            aris_sub = []
            for codigos in subamostras:
                Z_sub = escalar(matriz.loc[codigos], configuracao["padronizacao"])
                grupos_sub = agrupar(Z_sub, algoritmo, k)
                silhuetas_sub.append(silhouette_score(Z_sub, grupos_sub))
                aris_sub.append(adjusted_rand_score(grupos.loc[codigos], grupos_sub))
            resultados.append({"cenario": cenario, "algoritmo": algoritmo, "k": k, "grupos": grupos,
                               "silhueta": silhouette_score(Z, grupos),
                               "soma_quadrados_intra": soma_quadrados_intra(Z, grupos),
                               "silhueta_media_subamostras": np.mean(silhuetas_sub),
                               "ari_estabilidade_medio": np.mean(aris_sub),
                               "silhuetas_sub": silhuetas_sub, "aris_sub": aris_sub})
for resultado in resultados:
    for outro in resultados:
        if outro["cenario"] == resultado["cenario"] and outro["k"] == resultado["k"] and outro["algoritmo"] != resultado["algoritmo"]:
            resultado[f"ari_com_{outro['algoritmo']}"] = adjusted_rand_score(resultado["grupos"], outro["grupos"])
tabela = pd.DataFrame(resultados)[["cenario", "algoritmo", "k", "silhueta", "soma_quadrados_intra",
                                  "silhueta_media_subamostras", "ari_estabilidade_medio",
                                  "ari_com_kmeans", "ari_com_ward", "ari_com_kmedoids"]]
for cenario, configuracao in CENARIOS.items():
    print(f"\nCenário {cenario}: {configuracao['descricao']}")
    print(tabela[tabela["cenario"] == cenario].drop(columns="cenario").round(3).to_string(index=False))

figura, eixos = plt.subplots(len(CENARIOS), len(METRICAS), figsize=(18, 8))
for linha, (cenario, configuracao) in enumerate(CENARIOS.items()):
    for coluna, (metrica, titulo) in enumerate(METRICAS.items()):
        eixo = eixos[linha, coluna]
        for algoritmo in ALGORITMOS:
            pontos = tabela[(tabela["cenario"] == cenario) & (tabela["algoritmo"] == algoritmo)]
            eixo.plot(pontos["k"], pontos[metrica], marker="o", label=algoritmo)
        eixo.set_title(f"{cenario} · {configuracao['descricao']}\n{titulo}", fontsize=10)
        eixo.set_xlabel("k")
        eixo.legend()
figura.tight_layout()
figura.savefig(SAIDA / "metricas_por_cenario.png", dpi=150)

mlflow.set_tracking_uri("sqlite:///" + (RAIZ / "mlflow.db").as_posix())
if mlflow.get_experiment_by_name(EXPERIMENTO) is None:
    mlflow.create_experiment(EXPERIMENTO, artifact_location=(RAIZ / "mlruns").as_uri())
mlflow.set_experiment(EXPERIMENTO)
with mlflow.start_run(run_name="experimento_cenarios"):
    mlflow.set_tag("mlflow.note.content", "Dois cenários de preparação dos dados: as seis variáveis do modelo "
                   "padronizadas com escore z ou com mín-máx. Em cada cenário, K-means, Ward e K-medoides com k de 2 a 8, sobre os "
                   "144 municípios e sobre as mesmas 100 subamostras de 80%. Métricas: silhueta, soma de quadrados "
                   "intragrupo (cotovelo) e ARI. O experimento não escolhe: a escolha se faz lendo as métricas.")
    mlflow.log_params({"cenarios": ", ".join(CENARIOS), "algoritmos": ", ".join(ALGORITMOS), "valores_k": "2 a 8",
                       "municipios": len(municipios), "subamostras": N_SUBAMOSTRAS, "fracao_subamostra": FRACAO_SUBAMOSTRA})
    mlflow.log_figure(figura, "metricas_por_cenario.png")
    for cenario, configuracao in CENARIOS.items():
        with mlflow.start_run(run_name=f"{cenario} - {configuracao['descricao']}", nested=True):
            mlflow.log_params({"cenario": cenario, "variaveis": ", ".join(matriz.columns),
                               "padronizacao": configuracao["padronizacao"]})
            for resultado in resultados:
                if resultado["cenario"] == cenario:
                    with mlflow.start_run(run_name=f"{cenario}_{resultado['algoritmo']}_k{resultado['k']}", nested=True):
                        mlflow.log_params({"cenario": cenario, "padronizacao": configuracao["padronizacao"],
                                           "algoritmo": resultado["algoritmo"], "k": resultado["k"],
                                           **hiperparametros(resultado["algoritmo"])})
                        metricas = {"silhueta": resultado["silhueta"],
                                    "soma_quadrados_intra": resultado["soma_quadrados_intra"],
                                    "silhueta_media_subamostras": resultado["silhueta_media_subamostras"],
                                    "ari_estabilidade_medio": resultado["ari_estabilidade_medio"]}
                        for outro in ALGORITMOS:
                            if outro != resultado["algoritmo"]:
                                metricas[f"ari_com_{outro}"] = resultado[f"ari_com_{outro}"]
                        mlflow.log_metrics(metricas)
                        for b in range(N_SUBAMOSTRAS):
                            mlflow.log_metrics({"silhueta_subamostra": resultado["silhuetas_sub"][b],
                                                "ari_subamostra": resultado["aris_sub"][b]}, step=b)
plt.close(figura)

linhas_cenarios = []
for cenario, configuracao in CENARIOS.items():
    linhas_cenarios.append({"cenario": cenario, "descricao": configuracao["descricao"],
                            "variaveis": ", ".join(matriz.columns),
                            "padronizacao": configuracao["padronizacao"]})
tabela_cenarios = pd.DataFrame(linhas_cenarios)
execucoes = mlflow.search_runs(experiment_names=[EXPERIMENTO])
colunas = ["tags.mlflow.runName", "run_id", "tags.mlflow.parentRunId", "start_time"]
for coluna in execucoes.columns:
    if coluna.startswith("params."):
        colunas.append(coluna)
for coluna in execucoes.columns:
    if coluna.startswith("metrics.") and not coluna.endswith("_subamostra"):
        colunas.append(coluna)
tabela_execucoes = execucoes[colunas].sort_values("tags.mlflow.runName").copy()
tabela_execucoes["start_time"] = tabela_execucoes["start_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
novos_nomes = []
for coluna in colunas:
    novos_nomes.append(coluna.replace("tags.mlflow.", "").replace("params.", "").replace("metrics.", ""))
tabela_execucoes.columns = novos_nomes
cliente = MlflowClient()
linhas_subamostras = []
for _, execucao in execucoes.iterrows():
    silhuetas_registradas = cliente.get_metric_history(execucao["run_id"], "silhueta_subamostra")
    aris_registrados = cliente.get_metric_history(execucao["run_id"], "ari_subamostra")
    for silhueta, ari in zip(silhuetas_registradas, aris_registrados):
        linhas_subamostras.append({"execucao": execucao["tags.mlflow.runName"], "run_id": execucao["run_id"],
                                   "subamostra": silhueta.step, "silhueta": silhueta.value, "ari": ari.value})
tabela_subamostras = pd.DataFrame(linhas_subamostras).sort_values(["execucao", "subamostra"])
nomes_municipios = pd.read_csv(SAIDA / "indicadores_municipio.csv", index_col="cod_mun")["municipio"]
linhas_composicao = []
for b, codigos in enumerate(subamostras):
    for codigo in codigos:
        linhas_composicao.append({"subamostra": b, "cod_mun": codigo, "municipio": nomes_municipios[codigo]})
tabela_composicao = pd.DataFrame(linhas_composicao)
with pd.ExcelWriter(SAIDA / "registro_mlflow.xlsx") as planilha:
    tabela_cenarios.to_excel(planilha, sheet_name="cenarios", index=False)
    tabela_execucoes.to_excel(planilha, sheet_name="execucoes", index=False)
    tabela_subamostras.to_excel(planilha, sheet_name="subamostras", index=False)
    tabela_composicao.to_excel(planilha, sheet_name="composicao_subamostras", index=False)
print("Registro exportado para", SAIDA / "registro_mlflow.xlsx")
