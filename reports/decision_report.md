# Relatório de Decisão — Posicionamento de Preço no Airbnb do Rio

**Dados:** Inside Airbnb, snapshot de 2026-03-30, 39.816 anúncios ativos no Rio de Janeiro.
**Modelo:** regressão hedônica sobre o log do preço, com poder preditivo honesto de **adj. R² = 0,52** — explica cerca de metade da variação de preço; a outra metade é mercado e fatores não observados.

---

## Como ler este relatório

- O que entregamos é uma **faixa de posicionamento de preço**, não uma garantia de receita. O número-âncora é um ponto de partida, não um valor "certo".
- **Ocupação aqui é um proxy** (estimada a partir do volume de reviews). Não temos calendário real de reservas, então **nenhuma projeção de receita é uma promessa** — trate qualquer leitura de demanda como tendência, não como faturamento garantido.
- Preço de referência do mercado (todos os anúncios): mediana **R$ 500** (intervalo interquartil R$ 330 – R$ 827). É a régua geral; cada persona tem sua própria régua local.
- A faixa recomendada combina **50% modelo hedônico + 50% mediana de anúncios comparáveis** na vizinhança. Esse blend existe de propósito: com adj. R² = 0,52, nem o modelo sozinho nem o mercado sozinho decide o preço.

---

## O que move o preço no Rio

Drivers reais do modelo hedônico. O efeito é o impacto aproximado em % no preço, calculado como `exp(coef) − 1` — ou seja, "mantendo o resto igual, este atributo desloca o preço em cerca de tanto".

| Atributo | Efeito aproximado no preço | Direção |
|---|---|---|
| Sem histórico de reviews | **~ +35%** | sobe |
| + 1 banheiro | **~ +15%** | sobe |
| + 1 quarto | **~ +14%** | sobe |
| + 1 hóspede de capacidade | **~ +7%** | sobe |
| Quarto privado (vs. lugar inteiro) | **~ −24%** | desce |
| Quarto compartilhado (vs. lugar inteiro) | **~ −69%** | desce |

**Os maiores ganhos de preço vêm de espaço físico**: banheiros e quartos pesam mais que capacidade nominal de hóspedes. O sinal de "sem histórico de reviews" (+35%) reflete anúncios novos pedindo mais caro antes de terem reputação — é um padrão de mercado, não um conselho para esconder reviews.

### Destaque: ser Superhost NÃO é alavanca de preço

No modelo, o selo de **Superhost tem coeficiente negativo (~ −10%)**. Anúncios de Superhost tendem a estar associados a preços **mais baixos**, não mais altos — provavelmente porque Superhosts competem por ocupação/avaliação consistente, não por preço-prêmio.

> **Não recomendamos virar Superhost para cobrar mais caro.** O selo é sinal de outra coisa (consistência operacional, fidelização), não uma justificativa de preço. Tratar isso como caveat, nunca como tática de pricing.

---

## Recomendações por persona

Quatro perfis reais, com âncora, faixa de posicionamento, leitura de posição e número de anúncios comparáveis que sustentam a recomendação.

| Persona | Âncora | Faixa de posicionamento | Posição | Comparáveis |
|---|---|---|---|---|
| Copacabana · lugar inteiro · 2 hóspedes | **R$ 482** | R$ 360 – R$ 604 | em linha com o mercado | 1.882 |
| Ipanema · lugar inteiro · 4 hóspedes | **R$ 939** | R$ 668 – R$ 1.210 | acima do mercado | 1.482 |
| Copacabana · quarto privado · 2 hóspedes | **R$ 367** | R$ 226 – R$ 508 | em linha com o mercado | 1.202 |
| Barra da Tijuca · lugar inteiro · 6 hóspedes | **R$ 1.022** | R$ 692 – R$ 1.353 | acima do mercado | 637 |

- **Copacabana, lugar inteiro, 2 hóspedes:** se você tem um apê inteiro para 2 em Copacabana, posicione perto de **R$ 482** porque há 1.882 anúncios comparáveis e seu perfil está em linha com o mercado — espaço para subir só com diferencial real.
- **Ipanema, lugar inteiro, 4 hóspedes:** se você tem um apê inteiro para 4 em Ipanema, posicione na casa dos **R$ 939** porque o bairro sustenta preços acima do mercado e há 1.482 comparáveis confirmando esse patamar.
- **Copacabana, quarto privado, 2 hóspedes:** se você aluga um quarto privado para 2 em Copacabana, posicione perto de **R$ 367** porque o desconto de quarto privado (~ −24%) já está embutido e 1.202 comparáveis te colocam em linha com o mercado.
- **Barra da Tijuca, lugar inteiro, 6 hóspedes:** se você tem um apê inteiro para 6 na Barra, posicione na casa dos **R$ 1.022** porque capacidade alta + bairro sustentam preço acima do mercado — mas com 637 comparáveis (menos que as outras personas), trate a faixa larga (R$ 692 – R$ 1.353) com mais cautela.

> Sempre mire a **faixa**, não a âncora exata. Comece pela âncora, ajuste para cima com diferenciais concretos (vista, reforma, localização premium dentro do bairro) e para baixo se a ocupação proxy estiver fraca.

---

## Sazonalidade

Os dois picos datados de demanda no Rio são **Réveillon** (virada do ano) e **Carnaval**. São janelas em que o uplift de preço é claramente maior que a base.

> **As magnitudes do uplift são LIMITE INFERIOR.** Picos de horizonte distante batem em um teto de modelagem (0,699), então o efeito real desses eventos é **pelo menos** o que medimos — provavelmente maior. Use Réveillon e Carnaval como gatilhos para subir preço, mas não tome a magnitude estimada como o máximo possível.

---

## Limitações (ler antes de decidir)

1. **Poder preditivo moderado (adj. R² = 0,52).** O modelo explica ~metade da variação de preço. Por isso a recomendação é um **blend 50/50** modelo + mercado: nem o hedônico nem a mediana de comparáveis decide sozinho.
2. **Ocupação é proxy.** Estimada via reviews, não calendário real. **Nenhuma garantia de receita** — toda leitura de demanda é tendência, não faturamento.
3. **Snapshot único (2026-03-30).** A sazonalidade ampla pode estar confundida com o horizonte da coleta; magnitudes de eventos são limite inferior (ver acima).
4. **Sem sinal de comparáveis suficiente → sem percentil.** Quando não há anúncios comparáveis bastantes, o relatório diz "não há comparáveis suficientes" em vez de inventar uma posição mediana.
5. **Bairro fora do modelo → estimativa baseline.** Para bairros não modelados individualmente, a estimativa é genérica (baseline) e deve ser lida com cautela extra.

---

*Este relatório é uma ferramenta de posicionamento honesta: faixas, não promessas. O objetivo é te dar um ponto de partida defensável e os caveats para ajustá-lo — a decisão de preço final é sua.*
