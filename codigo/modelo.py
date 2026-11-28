"""Modelo de agrupamento (K-means, Ward, K-medoides e DBSCAN)"""
import numpy as np
import pandas as pd
from kmedoids import KMedoids
from scipy.cluster.hierarchy import linkage
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler, StandardScaler
SEMENTE = 42
N_INICIALIZACOES = 50
ALGORITMOS_K = ["kmeans", "ward", "kmedoids"]
VALORES_K = list(range(2, 9))
N_VALORES_EPS = 20
CONJUNTOS = {"completo": {"descricao": "Completo",
                          "variaveis": ["pop_0a4_pct", "pop_60m_pct",
                                        "agua_prec_pct", "agua_sem_pct",
                                        "esg_prec_pct", "esg_sem_pct"]},
             "saneamento": {"descricao": "Só saneamento",
                            "variaveis": ["agua_prec_pct", "agua_sem_pct",
                                          "esg_prec_pct", "esg_sem_pct"]},
             "exposicao_infantil": {"descricao": "Exposição infantil",
                                    "variaveis": ["agua_sem_pct", "esg_sem_pct",
                                                  "pop_0a4_pct"]}}
PADRONIZACOES = {"zscore": "Escore z", "minmax": "Mín-máx"}
VARIAVEIS_PERFIL = CONJUNTOS["completo"]["variaveis"]
NOMES = {"pop_0a4_pct": "Crianças 0-4 anos (%)", "pop_60m_pct": "Idosos 60+ (%)",
         "agua_prec_pct": "Água precária (%)", "agua_sem_pct": "Água sem atendimento (%)",
         "esg_prec_pct": "Esgoto precário (%)", "esg_sem_pct": "Esgoto sem atendimento (%)"}

def cenarios():
    """Cada cenário é um conjunto de variáveis com uma padronização"""
    lista = []
    for conjunto, configuracao in CONJUNTOS.items():
        for padronizacao, descricao in PADRONIZACOES.items():
            lista.append({"cenario": f"{conjunto}_{padronizacao}", "conjunto": conjunto,
                          "padronizacao": padronizacao, "variaveis": configuracao["variaveis"],
                          "descricao": f"{configuracao['descricao']} - {descricao}"})
    return lista

def escalar(dados, padronizacao):
    """Escore z ou mín-máx conforme o cenário"""
    if padronizacao == "zscore":
        escalador = StandardScaler()
    else:
        escalador = MinMaxScaler()
    escalador.set_output(transform="pandas")
    return escalador.fit_transform(dados)

def hiperparametros(algoritmo, n_variaveis=None):
    """Hiperparâmetros de cada algoritmo (DBSCAN: min_samples = 2 x número de variáveis)"""
    if algoritmo == "kmeans":
        return {"init": "k-means++", "n_init": N_INICIALIZACOES, "random_state": SEMENTE}
    if algoritmo == "kmedoids":
        return {"metric": "euclidean", "method": "pam", "init": "build"}
    if algoritmo == "dbscan":
        return {"metric": "euclidean", "min_samples": 2 * n_variaveis}
    return {"linkage": "ward"}

def agrupar(Z, algoritmo, k):
    """Agrupa as linhas de Z em k grupos; devolve o grupo de cada município e o modelo ajustado"""
    if algoritmo == "kmeans":
        modelo = KMeans(n_clusters=k, **hiperparametros("kmeans"))
    elif algoritmo == "kmedoids":
        modelo = KMedoids(n_clusters=k, **hiperparametros("kmedoids"))
    else:
        modelo = AgglomerativeClustering(n_clusters=k, **hiperparametros("ward"))
    grupos = modelo.fit_predict(Z.to_numpy())
    return pd.Series(grupos, index=Z.index), modelo

def agrupar_dbscan(Z, eps):
    """DBSCAN com o raio eps; o grupo -1 é ruído"""
    modelo = DBSCAN(eps=eps, **hiperparametros("dbscan", Z.shape[1]))
    grupos = modelo.fit_predict(Z.to_numpy())
    return pd.Series(grupos, index=Z.index), modelo

def distancias_vizinho(Z):
    """Distância de cada município ao seu k-ésimo vizinho (k = min_samples), em ordem crescente"""
    min_samples = hiperparametros("dbscan", Z.shape[1])["min_samples"]
    vizinhos = NearestNeighbors(n_neighbors=min_samples).fit(Z.to_numpy())
    distancias = vizinhos.kneighbors(Z.to_numpy())[0][:, -1]
    return np.sort(distancias)

def valores_eps(Z):
    """Valores de eps repartidos entre a menor e a maior distância ao k-ésimo vizinho"""
    distancias = distancias_vizinho(Z)
    return np.linspace(distancias.min(), distancias.max(), N_VALORES_EPS)

def arvore_ward(Z):
    """Árvore de uniões de Ward (matriz de ligação do dendrograma)"""
    return linkage(Z.to_numpy(), method="ward")

def altura_uniao(arvore, k):
    """Altura da união que passa de k para k - 1 grupos no dendrograma"""
    return arvore[-(k - 1), 2]

def numerar_por_tamanho(grupos):
    """Renomeia os grupos como G1, G2, ... do maior para o menor"""
    novos_nomes = {}
    for posicao, grupo in enumerate(grupos.value_counts().index):
        novos_nomes[grupo] = f"G{posicao + 1}"
    return grupos.map(novos_nomes)

def perfis(indicadores, grupos, colunas):
    """Mediana de cada indicador por grupo, mais a mediana do Pará e o tamanho de cada grupo"""
    tabela = indicadores[colunas].groupby(grupos).median()
    tabela.loc["Pará"] = indicadores[colunas].median()
    tabela["municipios"] = grupos.value_counts()
    tabela.loc["Pará", "municipios"] = len(grupos)
    populacao = indicadores["pop_total"].groupby(grupos).sum()
    tabela["populacao_pct"] = 100 * populacao / indicadores["pop_total"].sum()
    tabela.loc["Pará", "populacao_pct"] = 100.0
    return tabela.round(1)
