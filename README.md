# Binário: Acerto ou Erre — Kivy/Android

Jogo educacional de conversão decimal → binário com validação **bit a bit**.

## Regras

- Meta: 100 pontos.
- Bit correto: +5 pontos.
- Tentativa incorreta: -3 pontos, sem permitir pontuação abaixo de 0.
- O próximo bit só é liberado depois que o bit atual for corretamente resolvido.
- A partida termina depois de concluir a questão em que a meta de 100 pontos foi alcançada.

## Modos

- **Aprendizagem:** mostra os pesos binários (potências de 2).
- **Treinamento:** oculta os pesos.
- **Desafio:** oculta os pesos e concede 10 segundos por bit. Se o tempo esgotar, registra erro, aplica -3 e mantém a mesma posição.

## Recursos pedagógicos

- Cadastro simples por nome e turma.
- SQLite com histórico de estudantes, partidas, questões e cada tentativa.
- Registro da posição, dígito esperado, dígito tentado, peso binário e tempo de resposta.
- Erros agrupados por peso (1, 2, 4, 8, ... 128).
- Distinção entre erro ocasional e sequência persistente de erros na mesma posição.
- Percentual de precisão e de questões sem erro.
- Parecer pedagógico automático.
- Relatório `.txt` salvo no diretório privado do aplicativo.
- Histórico das últimas 50 partidas dentro do próprio app.
- Som opcional e vibração opcional no Android.

## Rodar no computador

Recomenda-se Python 3.11 ou 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Gerar APK no Linux

O Buildozer atual exige Python 3.10+ para seu ambiente de compilação. Instale as dependências indicadas pela documentação oficial para sua distribuição e, dentro da pasta do projeto:

```bash
pip install buildozer
buildozer -v android debug
```

O APK de depuração será colocado em `bin/` quando a compilação terminar.

Para uma versão de publicação, use o fluxo de release do Buildozer/python-for-android e assine o artefato conforme as exigências atuais da loja de destino.

## Dados no Android

O banco `binario_acerto_ou_erre.sqlite3` e a pasta `relatorios/` são criados em `App.user_data_dir`, que no Android aponta para o diretório gravável privado da aplicação. Assim, o jogo não depende de permissão de armazenamento externo.
