"""Perfis do modelo escolhido pelo usuário: python src/perfis.py <cenário> <algoritmo> <k>."""
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from modelo import CENARIOS, agrupar, escalar, numerar_por_tamanho, perfis
RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "data" / "output"
if len(sys.argv) != 4 or sys.argv[1] not in CENARIOS or sys.argv[2] not in ["kmeans", "ward", "kmedoids"] or not sys.argv[3].isdigit():
    sys.exit("Uso: python src/perfis.py <C1|C2> <kmeans|ward|kmedoids> <k>   por exemplo: python src/perfis.py C1 kmeans 4")
CENARIO = sys.argv[1]
ALGORITMO = sys.argv[2]
K = int(sys.argv[3])
if K < 2:
    sys.exit("O número de grupos k deve ser pelo menos 2")
NOMES = {"pop_0a4_pct": "Crianças 0-4 anos (%)", "pop_60m_pct": "Idosos 60+ (%)", "agua_adeq_pct": "Água adequada (%)",
         "agua_prec_pct": "Água precária (%)", "agua_sem_pct": "Água sem atendimento (%)",
         "esg_adeq_pct": "Esgoto adequado (%)", "esg_prec_pct": "Esgoto precário (%)", "esg_sem_pct": "Esgoto sem atendimento (%)"}

indicadores = pd.read_csv(SAIDA / "indicadores_municipio.csv", index_col="cod_mun")
configuracao = CENARIOS[CENARIO]
matriz = pd.read_csv(SAIDA / "matriz_modelo.csv", index_col="cod_mun")
Z = escalar(matriz, configuracao["padronizacao"])
grupos = numerar_por_tamanho(agrupar(Z, ALGORITMO, K))
colunas_perfil = ["pop_0a4_pct", "pop_60m_pct", "agua_adeq_pct", "agua_prec_pct", "agua_sem_pct",
                  "esg_adeq_pct", "esg_prec_pct", "esg_sem_pct", "rural_pct", "idade_pres_pct"]
tabela_perfis = perfis(indicadores, grupos, colunas_perfil)
atribuicao = indicadores[["municipio"]].copy()
atribuicao["grupo"] = grupos
tercis_rurais = pd.qcut(indicadores["rural_pct"], 3, labels=False)
ari_rural = adjusted_rand_score(grupos, tercis_rurais)
nome = f"{CENARIO}_{ALGORITMO}_k{K}"
atribuicao.to_csv(SAIDA / f"atribuicao_municipios_{nome}.csv")
tabela_perfis.to_csv(SAIDA / f"perfis_grupos_{nome}.csv")
print(tabela_perfis.T.to_string())
print(f"ARI entre a tipologia e os tercis de população rural (H3): {ari_rural:.3f}")

perfis_grupos = tabela_perfis.drop(index="Pará")
variaveis = list(matriz.columns)
figura, eixos = plt.subplots(1, len(variaveis), figsize=(3.2 * len(variaveis), 4))
for eixo, variavel in zip(eixos, variaveis):
    eixo.bar(perfis_grupos.index, perfis_grupos[variavel], color="#1d4e89")
    eixo.axhline(tabela_perfis.loc["Pará", variavel], color="#c1121f", linestyle="--", label="Pará")
    for posicao, valor in enumerate(perfis_grupos[variavel]):
        eixo.text(posicao, valor, f"{valor:.1f}".replace(".", ","), ha="center", va="bottom", fontsize=9)
    eixo.set_title(NOMES[variavel], fontsize=10)
eixos[0].legend()
figura.suptitle(f"Mediana de cada grupo e do Pará ({CENARIO}, {ALGORITMO}, k = {K})")
figura.tight_layout()
figura.savefig(SAIDA / f"perfis_dos_grupos_{nome}.png", dpi=150)
plt.close(figura)
print("Arquivos salvos em", SAIDA, "com o sufixo", nome)
