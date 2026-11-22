# Triagem de currículos por e-mail

Aplicação local que lê mensagens da caixa de entrada do Gmail com assunto contendo `VAGA`, guarda anexos PDF em disco, solicita uma análise indicativa ao provedor NVIDIA configurado e envia um relatório ao destinatário definido.

## Requisitos

- Python 3.10 ou superior.
- Conta Gmail com IMAP habilitado e OAuth 2.0 configurado no Google Cloud.
- Chave NVIDIA NIM e um modelo disponível para a conta.
- Critérios objetivos e atuais da vaga, revisados pela equipe responsável.

## Instalação

Na pasta do projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Preencha `EMAIL`, `DESTINATARIO` e `NVIDIA_API_KEY` em `.env`. Restrinja o arquivo a leitura do usuário (`chmod 600 .env` no Linux/macOS). Configure também `NVIDIA_MODEL`, `LIMITE_LOTE`, `INTERVALO_MINUTOS`, `DB_PATH` e `PDF_DIR` conforme o ambiente.

No Google Cloud, crie credenciais OAuth do tipo **Desktop app** e salve o arquivo como `credentials.json` nesta pasta. Proteja-o com permissões restritas. A primeira execução abre o fluxo OAuth no navegador e grava `token.json` com modo privado no POSIX. Não compartilhe esses arquivos nem os envie ao repositório.

## Executar

Um ciclo de verificação:

```bash
python automacao_run.py --once
```

Execução contínua (intervalo configurado no `.env`):

```bash
python automacao_run.py
```

Substituir o intervalo, em minutos:

```bash
python automacao_run.py --intervalo 30
```

A interface gráfica opcional é iniciada com `python config_gui.py` (requer Tkinter instalado no sistema).

## Testes

```bash
python -m unittest discover -v
```

Os testes usam doubles locais e não acessam Gmail nem o provedor de IA.

## Como funciona

### Fluxo principal

1. **Verificar caixa de entrada** — O sistema conecta-se ao IMAP do Gmail e busca emails não lidos com assunto contendo `VAGA` ou `Trabalhe Conosco`.
2. **Extrair PDF** — Se o email tiver anexo PDF, ele é salvo na pasta `pdfs/` com um nome único.
3. **Inserir no banco** — O currículo é registrado no SQLite com a `vaga` (nome da vaga) ou a `area_de_interesse` (para e-mails do tipo Trabalhe Conosco).
4. **Enviar para a IA** — Os PDFs são extraídos para texto e enviados para a NVIDIA NIM para análise.
5. **Gerar relatório** — A IA retorna um JSON com avaliações. O sistema gera um relatório HTML e envia por e-mail com os PDFs anexos.
6. **Marcar como lido e limpar** — O email é marcado como lido e os currículos processados são removidos do banco.

### Tipos de e-mail suportados

#### Formato atual (VAGA)

Assunto: `VAGA Nome da Vaga`

Corpo: contém PDF do currículo.

#### Novo formato: Trabalhe Conosco

Assunto: `Trabalhe Conosco -- Nova candidatura: Nome do candidato`

Corpo (exemplo):

```
Nome: Candidato exemplo
E-mail: exemplo@gmail.com
Telefone: 9999-9999
Data de nascimento: 1980-04-02T00:00:00
Cidade: exemplo
Endereço: endereço exemplo
Escolaridade: ensino medio completo
Área de interesse: Lojas - Estoque
Último cargo: OPERADOR LOGISTICO (MERCADO LIVRE)
Indicação: NÃO
Consentimento para recrutamento: true
Origem: trabalhe-conosco
```

**Diferença principal:** no formato `Trabalhe Conosco`, o campo `Área de interesse` substitui a `vaga` específica. A IA não reprova o candidato, apenas aloca no ranking da área de interesse correspondente quando o lote atinge 10 currículos, e recomenda revisão se necessário. As áreas de interesse suportadas são:

- Administrativo Fiscal
- Administrativo Marketing
- Administrativo Financeiro
- Administrativo Rh
- Comercial Vendas
- Comercial Caixa
- Lojas Estoque
- CD Estoque

---

## Variáveis de ambiente (.env)

| Variável | Descrição | Padrão |
|---|---|---|
| `EMAIL` | E-mail da conta que recebe os emails | obrigatório |
| `DESTINATARIO` | E-mail para enviar os relatórios | obrigatório |
| `NVIDIA_API_KEY` | Chave da API da NVIDIA | obrigatório |
| `NVIDIA_MODEL` | Modelo da NVIDIA NIM | `nvidia/nemotron-3-super-120b-a12b` |
| `NVIDIA_BASE_URL` | URL base da NVIDIA NIM | `https://integrate.api.nvidia.com/v1` |
| `LIMITE_LOTE` | Máximo de currículos por lote | `10` |
| `INTERVALO_MINUTOS` | Intervalo de verificação (minutos) | `60` |
| `INTERVALO_SEGUNDOS` | Intervalo em segundos (0 = usar minutos) | `0` |
| `MAX_PDFS_POR_EMAIL` | Máximo de PDFs por e-mail | `10` |
| `IA_TIMEOUT` | Timeout da requisição à IA (segundos) | `180` |
| `IA_TENTATIVAS` | Tentativas de retry da IA | `3` |
| `DB_PATH` | Caminho do banco SQLite | `triagem.db` |
| `PDF_DIR` | Pasta onde os PDFs são salvos | `pdfs` |
| `SCOPES` | Escopos OAuth do Gmail | `https://mail.google.com/` |

---

## Arquivos importantes

### `config.py`

Carrega e valida o `.env`. Contém as variáveis de ambiente usadas em todo o projeto e a função `validar_configuracao()` que retorna uma lista de problemas de configuração.

### `gmail.py`

- `obter_credenciais()` — Obtém as credenciais OAuth do Gmail (ou gera `token.json` na primeira execução).
- `conectar_imap(creds)` — Conecta-se ao servidor IMAP do Gmail.
- `buscar_nao_lidos(creds)` — Busca emails não lidos que contêm `VAGA` ou `Trabalhe Conosco` no assunto.
- `extrair_pdf(msg, pasta=None)` — Extrai PDFs do email e salva em `pdfs/`.
- `marcar_como_lido(creds, num_imap)` — Marca o email como lido.
- `enviar_email(assunto, html, anexos, anexo_html=None)` — Envia e-mail com PDF anexo.

### `db.py`

- `init()` — Cria as tabelas `curriculos` e `processados` no SQLite.
- `ja_processado(message_id)` — Verifica se um email já foi processado.
- `inserir_curriculo(...)` — Insere um currículo no banco.
- `vaga_com_lote_completo(limite)` — Retorna áreas que atingiram o limite de currículos.
- `processar_area(area, limite)` — Processa um lote de currículos de uma área.

### `ia.py`

- `avaliar_curriculos(vaga, curriculos_texto)` — Envia os textos dos currículos para a NVIDIA NIM e retorna o JSON de avaliação.
- `extrair_json(texto)` — Extrai o JSON da resposta da IA, lidando com markdown, pensamento do modelo e JSON truncado.
- `testar_conexao(api_key=None)` — Teste de conexão com a NVIDIA NIM.

### `report.py`

- `gerar_corpo_email(vaga, avaliacoes)` — Gera o corpo HTML do relatório.
- `gerar_anexo_relatorio(vaga, avaliacoes, arquivos_originais)` — Gera o relatório HTML completo em anexo.

### `automacao_run.py`

Ponto de entrada principal. Contém:

- `ciclo()` — Verifica a caixa de entrada e processa emails.
- `executar_loop(intervalo_segundos)` — Loop infinito com intervalo configurável.
- `main(argv)` — Ponto de entrada com argumentos de linha de comando.

---

## Salvaguardas

- Scores e recomendações são **apenas apoio à revisão humana**. Não devem ser usados como decisão automática de contratação ou eliminação.
- Envie currículos e dados pessoais apenas para destinatários autorizados e de acordo com a política de privacidade da organização.
- O banco SQLite e os PDFs ficam no disco local. Antes de produção, defina backup, retenção/exclusão, monitoramento e recuperação de falhas. Esta versão não foi projetada para múltiplas instâncias/processos concorrentes.
- O teste de integração real requer credenciais Gmail/OAuth e uma chave/modelo NVIDIA válidos. Não execute em produção antes de verificar permissões, critérios da vaga e destino dos relatórios.
