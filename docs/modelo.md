# O modelo de recomendação em detalhe

Implementação: `app/recommender.py`, classe `HybridRecommender`.

## Notação

- `U`: usuários, `I`: filmes
- `r(u,i)`: nota do usuário `u` para o filme `i` (0.5 a 5.0)
- `r̄(u)`: média das notas do usuário `u`
- `R(u)`: conjunto de filmes que `u` avaliou

## 1. Filtragem colaborativa item-item

**Matriz centralizada.** Para cada avaliação, guardamos `r(u,i) − r̄(u)`. Isso remove o viés
de usuários "generosos" ou "exigentes": o que importa é se o usuário gostou do filme
**mais ou menos do que costuma gostar**. O resultado é uma matriz esparsa `M` de
dimensão |I| × |U|.

**Similaridade entre filmes.** Cosseno entre as linhas de `M`:

```
sim(i, j) = (M_i · M_j) / (‖M_i‖ · ‖M_j‖)
```

Similaridades negativas são zeradas (só usamos vizinhos que se parecem de fato).

**Previsão.** Para um filme candidato `j`:

```
score_cf(u, j) = Σ_{i ∈ R(u)} sim(i, j) · (r(u,i) − r̄(u))  /  Σ_{i ∈ R(u)} sim(i, j)
```

Um score alto indica que o filme é parecido com filmes de que o usuário gostou acima da média.
Se todas as notas do usuário forem iguais (desvio zero), usamos `r(u,i) − 3` para não perder o sinal.

**Explicação.** O filme `i ∈ R(u)` que maximiza `sim(i, j) · (r(u,i) − r̄(u))` é o que
"mais puxou" a recomendação: *"Porque você gostou de i"*.

**Eficiência.** Não pré-calculamos a matriz |I| × |I| inteira. Para cada pedido, calculamos
só as |R(u)| linhas necessárias, o que custa O(|R(u)| · nnz(M)).

## 2. Filtragem baseada em conteúdo

**Vetor do filme.** TF-IDF sobre os gêneros, em que cada gênero é um termo. O IDF dá mais peso
a gêneros raros (por exemplo "Film-Noir") do que a gêneros comuns ("Drama"), que dizem menos
sobre o gosto de alguém.

**Perfil do usuário.**

```
p(u) = normalizar( Σ_{i ∈ R(u)} (r(u,i) − r̄(u)) · v(i) )  +  normalizar( tfidf(gêneros favoritos) )
```

Filmes que o usuário avaliou acima da própria média puxam o perfil na direção dos seus gêneros;
filmes avaliados abaixo empurram para longe. Os gêneros favoritos declarados no cadastro somam
ao perfil, o que permite recomendar já no primeiro acesso.

**Score.** `score_cb(u, j) = cos(p(u), v(j))`.

**Explicação.** Os gêneros do filme com maior peso positivo no perfil:
*"Combina com os gêneros que você curte: Horror, Mystery"*.

## 3. Popularidade (média bayesiana)

```
pop(j) = (n_j · média_j + m · C) / (n_j + m)
```

`n_j` é o número de avaliações do filme, `C` a média global e `m = 5` a força da "prior".
Um filme com uma única nota 5.0 fica próximo da média global até acumular mais avaliações.
É usada como fallback quando não há nenhuma informação sobre o usuário e, com peso mínimo
(0,001), como critério de desempate.

## 4. Combinação

Antes de combinar, os dois scores são normalizados para [0, 1] (min-max) considerando apenas
os filmes candidatos, isto é, os que o usuário ainda não avaliou.

```
alpha = min(1, |R(u)| / CF_FULL_WEIGHT_AT)       # padrão: 20
score(u, j) = alpha · score_cf(u, j) + (1 − alpha) · score_cb(u, j)
```

| Situação do usuário | Estratégia usada (`strategy_used`) |
|---|---|
| Sem avaliações e sem gêneros favoritos | `popular` |
| Sem avaliações, com gêneros favoritos | `content` |
| Poucas avaliações | `hybrid`, com peso maior no conteúdo |
| 20 avaliações ou mais | `hybrid`, essencialmente colaborativa |

## 5. Itens similares

`/items/{id}/similar` faz a média (após normalização) entre a similaridade de conteúdo
(cosseno dos vetores TF-IDF) e a similaridade colaborativa (cosseno das linhas de `M`).

## Limitações e próximos passos

- **Novos filmes sem avaliações** só aparecem pelo conteúdo (gêneros). Usar sinopses ou tags
  do MovieLens (`tags.csv`) deixaria o conteúdo mais rico.
- **Escala.** O retreino completo é adequado para o MovieLens small (< 1 s). Para milhões de
  avaliações, o caminho seria fatoração de matrizes (SVD/ALS) treinada em segundo plano.
- **Avaliação offline.** Uma extensão natural é medir Precision@K e Recall@K separando parte
  das avaliações de cada usuário como teste.
