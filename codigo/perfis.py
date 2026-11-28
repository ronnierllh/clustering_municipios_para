"""Perfis da combinação escolhida pelo analista depois de ler os resultados do experimento no MLflow.
Execução: python codigo/perfis.py   (a escolha fica nas constantes abaixo)"""
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.decomposition import PCA
from modelo import (ALGORITMOS_K, CONJUNTOS, NOMES, PADRONIZACOES, VALORES_K,
                    VARIAVEIS_PERFIL, agrupar, escalar, numerar_por_tamanho, perfis)

CONJUNTO = "completo"
PADRONIZACAO = "zscore"
ALGORITMO = "kmeans"
K = 4

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "dados" / "saidas"
CORES = ["#1d4e89", "#c8641a", "#2a9d8f", "#c1121f", "#6a4c93", "#b5179e", "#588157", "#5c677d"]
N_VARIAVEIS_ROTULO = 4
if CONJUNTO not in CONJUNTOS:
    sys.exit(f"CONJUNTO inválido: {CONJUNTO}. Opções: {', '.join(CONJUNTOS)}")
if PADRONIZACAO not in PADRONIZACOES:
    sys.exit(f"PADRONIZACAO inválida: {PADRONIZACAO}. Opções: {', '.join(PADRONIZACOES)}")
if ALGORITMO not in ALGORITMOS_K:
    sys.exit(f"ALGORITMO inválido: {ALGORITMO}. Opções: {', '.join(ALGORITMOS_K)}")
if K not in VALORES_K:
    sys.exit(f"K deve ser um inteiro entre {VALORES_K[0]} e {VALORES_K[-1]}, o alcance do experimento")

try:
    indicadores = pd.read_csv(SAIDA / "indicadores_municipio.csv", index_col="cod_mun")
except FileNotFoundError:
    sys.exit("Falta dados/saidas/indicadores_municipio.csv. Execute antes: python codigo/preprocessamento.py")

variaveis = CONJUNTOS[CONJUNTO]["variaveis"]
Z = escalar(indicadores[variaveis], PADRONIZACAO)
grupos = numerar_por_tamanho(agrupar(Z, ALGORITMO, K)[0])
tabela_perfis = perfis(indicadores, grupos, VARIAVEIS_PERFIL)
atribuicao = indicadores[["municipio"]].copy()
atribuicao["grupo"] = grupos
atribuicao.to_csv(SAIDA / "atribuicao_municipios.csv")
tabela_perfis.to_csv(SAIDA / "perfis_grupos.csv")
print(tabela_perfis.T.to_string())

acp = PCA().fit(Z)
pontos = acp.transform(Z)
variacao = 100 * acp.explained_variance_ratio_
pesos = pd.DataFrame(acp.components_[:2].T, index=variaveis, columns=["Comp. 1", "Comp. 2"])
print("\nPeso de cada variável nos dois eixos da ACP:")
print(pesos.round(2).to_string())

def rotulo_eixo(componente, numero):
    maiores = pesos[componente].abs().sort_values(ascending=False).index[:N_VARIAVEIS_ROTULO]
    positivas = [NOMES[v].replace(" (%)", "") for v in maiores if pesos.loc[v, componente] > 0]
    negativas = [NOMES[v].replace(" (%)", "") for v in maiores if pesos.loc[v, componente] < 0]
    lados = []
    if negativas:
        lados.append(f"← {' - '.join(negativas)}")
    if positivas:
        lados.append(f"{' - '.join(positivas)} →")
    return f"Componente {numero} ({variacao[numero - 1]:.0f} % da variação)\n" + "      ".join(lados)

figura, eixo = plt.subplots(figsize=(9, 6.5))
for posicao, grupo in enumerate(tabela_perfis.index.drop("Pará")):
    cor = CORES[posicao % len(CORES)]
    selecao = (grupos == grupo).to_numpy()
    eixo.scatter(pontos[selecao, 0], pontos[selecao, 1], s=28, color=cor, alpha=0.65, edgecolor="white",
                 linewidth=0.5, label=grupo)
    x, y = pontos[selecao, :2].mean(axis=0)
    eixo.scatter(x, y, marker="X", s=260, color=cor, edgecolor="black", linewidth=1.4, zorder=5)
eixo.scatter([], [], marker="X", s=130, color="white", edgecolor="black", label="Centroide")
eixo.axhline(0, color="#cccccc", linewidth=0.8, zorder=0)
eixo.axvline(0, color="#cccccc", linewidth=0.8, zorder=0)
eixo.set_xlabel(rotulo_eixo("Comp. 1", 1), fontsize=9)
eixo.set_ylabel(rotulo_eixo("Comp. 2", 2), fontsize=9)
eixo.spines[["top", "right"]].set_visible(False)
eixo.legend(frameon=False, fontsize=9)
eixo.set_title(f"{CONJUNTOS[CONJUNTO]['descricao']} - {PADRONIZACOES[PADRONIZACAO]} - {ALGORITMO} - k = {K}",
               fontsize=11)
figura.tight_layout()
figura.savefig(SAIDA / "grupos_acp.png", dpi=150)
plt.close(figura)

