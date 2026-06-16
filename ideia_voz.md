# Ideia — Geração de Podcasts de Estudo por Voz

> Ideia discutida em 2026-06-16. Aplicação planejada para futuro próximo.

---

## O Conceito

Gerar arquivos de **podcast de estudo** separados por episódios, onde cada episódio cobre um subtema dentro do tema principal.

**Exemplo:**
- Tema: Empreendedorismo
- Episódio 1: Mentalidade Empreendedora
- Episódio 2: Fases de Sprint / Ciclo de Startup
- Episódio 3: Pensamento Empreendedor e suas Conexões

---

## Formato de Áudio Mais Eficaz para Aprendizado

### Comparativo de Formatos

| Formato | Retenção | Engajamento | Profundidade | Melhor para |
|---|---|---|---|---|
| Aula monologue | Baixa | Baixo | Alta | Quem já sabe o básico |
| Feynman narrado | Média | Médio | Baixa | Conceitos simples |
| **Diálogo Socrático** (A ensina, B pergunta) | **Alta** | **Alto** | Média-Alta | **Revisão ativa** |
| Debate de especialistas | Média | Muito alto | Média | Nuances e controvérsias |
| Story-case (conceito em problema real) | Alta | Alto | Média | Aplicação prática |

### Recomendação: Diálogo Socrático Híbrido

O mesmo formato que o NotebookLM usa (apresentador ensina, aprendiz pergunta), mas com três tipos de perguntas específicos:

1. **"Por quê?"** — força explicação causal (elaborative interrogation)
2. **"E se...?"** — edge cases, limites do conceito
3. **"Isso se conecta com X que vimos antes?"** — bridging entre episódios

Isso transforma o podcast em um **ensaio ativo por procuração** — o ouvinte acompanha o processo de pensar, não apenas respostas prontas.

---

## Opções de Implementação

### Opção A — Scripts .md (mais simples, zero dependência)
Gerar scripts de diálogo em `<pasta>/podcast/episodio_<n>_<subtema>.md` com marcadores `[Apresentador]:` e `[Aprendiz]:`. O usuário usa qualquer TTS externo.

### Opção B — TTS via `edge-tts` (gratuito, local)
```bash
pip install edge-tts
```
- Vozes PT-BR: `pt-BR-FranciscaNeural` (apresentadora) e `pt-BR-AntonioNeural` (aprendiz)
- Gera `.mp3` por bloco de fala, depois concatena com `pydub`
- Zero custo, funciona offline

### Opção C — OpenAI TTS API
- Vozes de alta qualidade (`nova`, `onyx`)
- ~$0.015/1k chars ≈ $0.30 por episódio de 10 min
- Requer chave de API OpenAI

---

## Plano de Implementação Sugerido

1. **Fase A** (imediato quando implementar): Scripts `.md` com diálogo socrático como nova fase do pipeline (Fase 10)
   - Input: arquivos .md de um subtema
   - Output: `<pasta>/podcast/episodio_<n>_<subtema>.md`
   - LLM gera o script no formato `[Apresentador]: ... \n[Aprendiz]: ...`

2. **Fase B** (evolução): Integrar `edge-tts` para gerar `.mp3` reais com duas vozes diferentes

3. **Fase C** (premium): Opção de usar OpenAI TTS para qualidade máxima

---

## Notas de Implementação

- Cada episódio deve ter ~15-20 min de áudio (em script: ~2000-3000 palavras)
- Incluir timestamps marcados no script para navegação
- O script pode servir como material de leitura mesmo sem TTS
- Adicionar link para `podcast/` na sidebar dos HTMLs de conceito
