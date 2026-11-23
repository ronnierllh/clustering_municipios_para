"""Modelo de agrupamento (K-means, Ward e K-medoides)"""
import pandas as pd
from kmedoids import KMedoids
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.preprocessing import MinMaxScaler, StandardScaler
SEMENTE = 42
N_INICIALIZACOES = 50
CENARIOS = {"C1": {"padronizacao": "zscore", "descricao": "Escore z"},
            "C2": {"padronizacao": "minmax", "descricao": "Mín-máx"}}

def escalar(dados, padronizacao):
    """Escore z ou mín-máx conforme o cenário."""
    if padronizacao == "zscore":
        escalador = StandardScaler()
    else:
        escalador = MinMaxScaler()
    escalador.set_output(transform="pandas")
    return escalador.fit_transform(dados)

def hiperparametros(algoritmo):
    """Hiperparâmetros de cada algoritmo"""
    if algoritmo == "kmeans":
        return {"init": "k-means++", "n_init": N_INICIALIZACOES, "random_state": SEMENTE}
    if algoritmo == "kmedoids":
        return {"metric": "euclidean", "method": "pam", "init": "build", "random_state": SEMENTE}
    return {"linkage": "ward"}

def agrupar(Z, algoritmo, k):
    """Agrupa as linhas de Z em k grupos e devolve o grupo de cada município"""
    if algoritmo == "kmeans":
        modelo = KMeans(n_clusters=k, **hiperparametros("kmeans"))
    elif algoritmo == "kmedoids":
        modelo = KMedoids(n_clusters=k, **hiperparametros("kmedoids"))
    else:
        modelo = AgglomerativeClustering(n_clusters=k, **hiperparametros("ward"))
    grupos = modelo.fit_predict(Z.to_numpy())
    return pd.Series(grupos, index=Z.index)

def soma_quadrados_intra(Z, grupos):
    """Soma das distâncias ao quadrado de cada município ao centro do seu grupo"""
    total = 0.0
    for grupo in grupos.unique():
        membros = Z[grupos == grupo]
        total += ((membros - membros.mean()) ** 2).sum().sum()
    return total

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
