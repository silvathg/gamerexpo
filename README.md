# GamerExpo v1

**GamerExpo v1** é uma aplicação em Python com interface em Streamlit para diagnóstico de hardware com foco em jogos.

A ferramenta identifica informações do computador do usuário, gera relatórios em `.json` e `.txt` e prepara os dados para uma segunda etapa de recomendação de jogos, configurações gráficas e possíveis upgrades.

## Objetivo

Ajudar o usuário a responder:

> Quais jogos meu computador consegue rodar e em quais configurações?

## Funcionalidades

- Diagnóstico de hardware local
- Identificação de CPU, GPU, RAM, armazenamento, sistema operacional e DirectX
- Geração de relatório em `.json`
- Geração de relatório em `.txt`
- Análise inicial do perfil gamer da máquina
- Base para recomendação de jogos a partir do diagnóstico

## Tecnologias

- Python
- PowerShell / WMI / CIM
- JSON
- TXT

## Fluxo da Aplicação

```text
Abrir aplicação
↓
Iniciar diagnóstico
↓
Coletar dados da máquina
↓
Exibir relatório
↓
Salvar em JSON ou TXT
↓
Usar JSON para recomendar jogos e configurações
```

## Estrutura Sugerida

```text
gamerexpo/
├── app.py
├── diagnostic.py
├── game_recommender.py
├── requirements.txt
├── reports/
└── README.md
```

## Instalação

Clone o repositório:
```bash
git clone https://github.com/silvathg/gamerexpo.git
```

Acesse a pasta:

```bash
cd gamerexpo
```

Crie um ambiente virtual:

```bash
python -m venv .venv
```

Ative o ambiente virtual no Windows:

```bash
.venv\Scripts\activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

## Execução

Rode a aplicação com:
```bash
python app.py
```
