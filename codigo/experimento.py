"""Plano de experimentação"""
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import mlflow
from mlflow.tracking import MlflowClient
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram
from sklearn.metrics import adjusted_rand_score, davies_bouldin_score, silhouette_score
from modelo import (ALGORITMOS_K, CONJUNTOS, PADRONIZACOES, VALORES_K,
                    N_VALORES_EPS, agrupar, agrupar_dbscan, altura_uniao,
                    arvore_ward, cenarios, distancias_vizinho, escalar,
                    hiperparametros, valores_eps)

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "dados" / "saidas"
FIGURAS = SAIDA / "figuras"
EXPERIMENTO = "tipologia_municipios_para"
CORES = {"kmeans": "#1d4e89", "ward": "#c8641a", "kmedoids": "#6a4c93"}
NOMES_ALGORITMOS = {"kmeans": "K-means", "ward": "Ward", "kmedoids": "K-medoides"}

try:
    indicadores = pd.read_csv(SAIDA / "indicadores_municipio.csv", index_col="cod_mun")
except FileNotFoundError:
    sys.exit("Falta dados/saidas/indicadores_municipio.csv. Execute antes: python codigo/preprocessamento.py")

FIGURAS.mkdir(parents=True, exist_ok=True)
print(f"Indicadores: {indicadores.shape[0]} municípios")

def metricas_comuns(Z, grupos):
    """Silhueta e Davies-Bouldin sobre os municípios agrupados"""
    agrupados = grupos != -1
    if grupos[agrupados].nunique() < 2:
        return np.nan, np.nan
    return (silhouette_score(Z[agrupados], grupos[agrupados]),
            davies_bouldin_score(Z[agrupados], grupos[agrupados]))

resultados = []
dbscan = []
arvores = {}
for cenario in cenarios():
    Z = escalar(indicadores[cenario["variaveis"]], cenario["padronizacao"])
    arvore = arvore_ward(Z)
    arvores[cenario["cenario"]] = arvore
    for algoritmo in ALGORITMOS_K:
        for k in VALORES_K:
            grupos, modelo = agrupar(Z, algoritmo, k)
            silhueta, davies_bouldin = metricas_comuns(Z, grupos)
            resultado = {**cenario, "algoritmo": algoritmo, "k": k, "grupos": grupos,
                         "silhueta": silhueta, "davies_bouldin": davies_bouldin}
            if algoritmo == "kmeans":
                resultado["inercia"] = modelo.inertia_
            elif algoritmo == "kmedoids":
                resultado["perda"] = modelo.inertia_
            else:
                resultado["altura_uniao"] = altura_uniao(arvore, k)
            resultados.append(resultado)
    for posicao, eps in enumerate(valores_eps(Z)):
        grupos, modelo = agrupar_dbscan(Z, eps)
        silhueta, davies_bouldin = metricas_comuns(Z, grupos)
        dbscan.append({**cenario, "passo": posicao, "eps": eps,
                       "min_samples": hiperparametros("dbscan", Z.shape[1])["min_samples"],
                       "n_grupos": grupos[grupos != -1].nunique(), "ruido_pct": 100 * (grupos == -1).mean(),
                       "silhueta": silhueta, "davies_bouldin": davies_bouldin})

for resultado in resultados:
    for outro in resultados:
        mesmo_lugar = outro["cenario"] == resultado["cenario"] and outro["k"] == resultado["k"]
        if mesmo_lugar and outro["algoritmo"] != resultado["algoritmo"]:
            resultado[f"ari_com_{outro['algoritmo']}"] = adjusted_rand_score(resultado["grupos"], outro["grupos"])
        referencia = (outro["conjunto"] == "completo" and outro["padronizacao"] == resultado["padronizacao"]
                      and outro["algoritmo"] == resultado["algoritmo"] and outro["k"] == resultado["k"])
        if referencia and resultado["conjunto"] != "completo":
            resultado["ari_com_completo"] = adjusted_rand_score(resultado["grupos"], outro["grupos"])
        outra_padronizacao = (outro["conjunto"] == resultado["conjunto"] and outro["padronizacao"] != resultado["padronizacao"]
                              and outro["algoritmo"] == resultado["algoritmo"] and outro["k"] == resultado["k"])
        if outra_padronizacao:
            resultado["ari_com_outra_padronizacao"] = adjusted_rand_score(resultado["grupos"], outro["grupos"])
tabela = pd.DataFrame(resultados).drop(columns=["grupos", "variaveis"])
tabela_dbscan = pd.DataFrame(dbscan).drop(columns="variaveis")

def figura_cotovelo(pontos, metrica, titulo, rotulo_y, cor):
    """Cotovelo"""
    figura, eixo = plt.subplots(figsize=(6, 4))
    eixo.plot(pontos["k"], pontos[metrica], marker="o", color=cor)
    eixo.set_title(titulo)
    eixo.set_xlabel("k")
    eixo.set_ylabel(rotulo_y)
    eixo.set_xticks(VALORES_K)
    eixo.spines[["top", "right"]].set_visible(False)
    figura.tight_layout()
    return figura

def figura_dendrograma(arvore, titulo):
    """Dendrograma de Ward"""
    figura, eixo = plt.subplots(figsize=(7, 4.5))
    dendrogram(arvore, ax=eixo, truncate_mode="lastp", p=VALORES_K[-1] * 2, color_threshold=0,
               above_threshold_color=CORES["ward"])
    eixo.set_title(titulo)
    eixo.set_ylabel("Altura da união")
    eixo.set_xlabel("Ramos")
    eixo.spines[["top", "right"]].set_visible(False)
    figura.tight_layout()
    return figura

def figura_distancias(distancias, min_samples, titulo):
    """Distancia de cada município ao k-ésimo vizinho"""
    figura, eixo = plt.subplots(figsize=(6, 4))
    eixo.plot(range(1, len(distancias) + 1), distancias, color="#333333")
    eixo.set_title(titulo)
    eixo.set_xlabel("Municípios em ordem crescente")
    eixo.set_ylabel(f"Distancia ao {min_samples}º vizinho")
    eixo.spines[["top", "right"]].set_visible(False)
    figura.tight_layout()
    return figura

def figura_silhueta_db(linhas, titulo):
    """Silhueta e Davies-Bouldin contra k, uma linha por algoritmo"""
    figura, eixos = plt.subplots(1, 2, figsize=(11, 4))
    for eixo, (metrica, nome) in zip(eixos, [("silhueta", "Silhueta"),
                                            ("davies_bouldin", "Davies-Bouldin")]):
        for algoritmo in ALGORITMOS_K:
            pontos = linhas[linhas["algoritmo"] == algoritmo]
            eixo.plot(pontos["k"], pontos[metrica], marker="o", color=CORES[algoritmo],
                      label=NOMES_ALGORITMOS[algoritmo])
        eixo.set_title(nome)
        eixo.set_xlabel("k")
        eixo.set_xticks(VALORES_K)
        eixo.spines[["top", "right"]].set_visible(False)
        eixo.legend()
    figura.suptitle(titulo)
    figura.tight_layout()
    return figura

def figuras_cenario(cenario, Z, linhas, arvore):
    """Graficos x cenario"""
    min_samples = hiperparametros("dbscan", Z.shape[1])["min_samples"]
    titulo = cenario["descricao"]
    figuras = {"distancias_dbscan": figura_distancias(distancias_vizinho(Z), min_samples, f"DBSCAN - {titulo}")}
    if cenario["conjunto"] == "completo":
        kmeans = linhas[linhas["algoritmo"] == "kmeans"]
        kmedoids = linhas[linhas["algoritmo"] == "kmedoids"]
        figuras["cotovelo_kmeans"] = figura_cotovelo(kmeans, "inercia", f"K-means - {titulo}", "Inércia",
                                                     CORES["kmeans"])
        figuras["cotovelo_kmedoids"] = figura_cotovelo(kmedoids, "perda", f"K-medoides - {titulo}", "Perda",
                                                       CORES["kmedoids"])
        figuras["dendrograma_ward"] = figura_dendrograma(arvore, f"Ward - {titulo}")
        figuras["silhueta_davies_bouldin"] = figura_silhueta_db(linhas, titulo)
    return figuras

mlflow.set_tracking_uri("sqlite:///" + (RAIZ / "mlflow.db").as_posix())
if mlflow.get_experiment_by_name(EXPERIMENTO) is None:
    mlflow.create_experiment(EXPERIMENTO, artifact_location=(RAIZ / "mlruns").as_uri())
experimento = mlflow.set_experiment(EXPERIMENTO)
cliente = MlflowClient()
anteriores = cliente.search_runs([experimento.experiment_id], max_results=50000)
for execucao in anteriores:
    cliente.delete_run(execucao.info.run_id) 
if anteriores:
    print(f"{len(anteriores)} execuções anteriores arquivadas no MLflow")
with mlflow.start_run(run_name="experimento_cenarios"):
    mlflow.set_tag("mlflow.note.content", "Seis cenários: tres conjuntos de variáveis (completo, só saneamento e exposição infantil), duas padronizacoes (escore z e min-max), quatro algoritmos (K-means, Ward, K-medoides e DBSCAN)")
    mlflow.log_params({"conjuntos": ", ".join(CONJUNTOS), "padronizacoes": ", ".join(PADRONIZACOES),
                       "algoritmos": ", ".join(ALGORITMOS_K + ["dbscan"]), "valores_k": "2 a 8",
                       "valores_eps": N_VALORES_EPS, "municipios": len(indicadores)})
    for cenario in cenarios():
        with mlflow.start_run(run_name=cenario["descricao"], nested=True):
            mlflow.log_params({"cenario": cenario["cenario"], "conjunto": cenario["conjunto"],
                               "padronizacao": cenario["padronizacao"], "variaveis": ", ".join(cenario["variaveis"])})
            Z = escalar(indicadores[cenario["variaveis"]], cenario["padronizacao"])
            linhas = tabela[tabela["cenario"] == cenario["cenario"]]
            for nome, figura in figuras_cenario(cenario, Z, linhas, arvores[cenario["cenario"]]).items():
                mlflow.log_figure(figura, f"{nome}.png")
                figura.savefig(FIGURAS / f"{cenario['cenario']}_{nome}.png", dpi=150)
                plt.close(figura)
            for resultado in resultados:
                if resultado["cenario"] != cenario["cenario"]:
                    continue
                with mlflow.start_run(run_name=f"{cenario['cenario']}_{resultado['algoritmo']}_k{resultado['k']}",
                                      nested=True):
                    mlflow.log_params({"cenario": cenario["cenario"], "conjunto": cenario["conjunto"],
                                       "padronizacao": cenario["padronizacao"], "algoritmo": resultado["algoritmo"],
                                       "k": resultado["k"], **hiperparametros(resultado["algoritmo"])})
                    metricas = {}
                    for nome in ["silhueta", "davies_bouldin", "inercia", "perda", "altura_uniao", "ari_com_kmeans",
                                 "ari_com_ward", "ari_com_kmedoids", "ari_com_completo", "ari_com_outra_padronizacao"]:
                        if nome in resultado:
                            metricas[nome] = resultado[nome]
                    mlflow.log_metrics(metricas)
            with mlflow.start_run(run_name=f"{cenario['cenario']}_dbscan", nested=True):
                passos = tabela_dbscan[tabela_dbscan["cenario"] == cenario["cenario"]]
                mlflow.log_params({"cenario": cenario["cenario"], "conjunto": cenario["conjunto"],
                                   "padronizacao": cenario["padronizacao"], "algoritmo": "dbscan",
                                   "eps": f"{N_VALORES_EPS} valores de {passos['eps'].min():.3f} a {passos['eps'].max():.3f}",
                                   **hiperparametros("dbscan", len(cenario["variaveis"]))})
                for _, passo in passos.iterrows():
                    mlflow.log_metrics({"eps": passo["eps"], "n_grupos": passo["n_grupos"],
                                        "ruido_pct": passo["ruido_pct"], "silhueta": passo["silhueta"],
                                        "davies_bouldin": passo["davies_bouldin"]}, step=int(passo["passo"]))

