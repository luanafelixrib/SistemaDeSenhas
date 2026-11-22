# Sistema de Senhas para Clínica Médica

Sistema acadêmico em Python para organizar a fila de atendimento de uma clínica médica por especialidade e prioridade. O projeto está sendo desenvolvido passo a passo pelos integrantes do grupo, com foco em modularização e no uso de estruturas de dados.

> **Estado atual:** o sistema está completo e funciona em duas interfaces: janela (Tkinter) e terminal. Os modelos, o cadastro de especialistas (com autenticação do administrador), as filas por especialidade, o painel, o SQLite, o relatório diário em `.txt` (com consulta por data) e a exportação em CSV e Excel estão implementados e testados, e o `main.py` integra tudo. Ao reabrir o programa no meio do dia, as filas voltam do banco.

## Objetivos

- Emitir senhas normais e prioritárias para cada especialidade.
- Organizar as senhas prioritárias por prioridade e ordem de chegada, mantendo as normais em ordem FIFO.
- Permitir que especialistas chamem pacientes para seus consultórios.
- Exibir informações da chamada e uma estimativa de espera.
- Registrar os atendimentos do dia em SQLite e gerar um relatório diário.

## Especialidades e prioridades

As especialidades disponíveis no modelo atual são Clínica Geral, Pediatria, Ginecologia e Cardiologia, conforme o enunciado. Cada especialidade comporta até três especialistas e a clínica tem 12 consultórios (4 × 3 = 12). Como o código percorre o enum `Especialidade`, incluir uma nova especialidade exige alterar o enum e rever o total de consultórios.

| Código | Prioridade |
| --- | --- |
| 1 | Idosos com 80 anos ou mais |
| 2 | Idosos de 60 a 79 anos |
| 3 | Pessoas com deficiência (PCD) |
| 4 | Gestantes |
| 5 | Pessoas obesas |
| 6 | Crianças no colo |
| 7 | Senha normal |

Os códigos 1 a 6 representam as prioridades previstas no projeto. O código 2 (idosos de 60 a 79 anos) e a regra de prioridade estrita foram definidos pelo grupo e já estão implementados no código. O código 7 representa a senha normal no enum. As senhas normais não entram no heap: ficam em uma fila FIFO (`deque`) e só são chamadas quando não há senha prioritária aguardando.

## Tecnologias previstas

- Python 3.10 ou superior.
- `dataclasses` e `Enum` para os modelos.
- `heapq` para as filas de prioridade.
- `collections.deque` para manter as senhas normais em ordem FIFO.
- `sqlite3` para persistir os dados do dia.
- `csv`, `zipfile` e `xml.etree` para gerar os relatórios em CSV e Excel (`.xlsx`), sem bibliotecas externas.
- Tkinter para a interface gráfica.

As bibliotecas citadas fazem parte da biblioteca padrão do Python; não há dependências externas definidas até o momento.

## Organização dos módulos

O código fica no pacote `clinica/`, com uma pasta por módulo do enunciado. Cada pasta tem um `__init__.py` que indica o que os outros módulos podem usar, então quem importa não precisa saber em qual arquivo cada classe está. O `main.py` fica na raiz.

```
Clinica-SistemaSenhaPrioridade/
├── main.py
├── clinica/
│   ├── sistema.py        integra cadastro, filas, painel, banco e relatório
│   ├── modelos/          enums.py, entidades.py
│   ├── especialistas/    cadastro.py, administrador.py
│   ├── filas/            fila_especialidade.py, gerenciador.py
│   ├── painel/           painel.py
│   ├── relatorio/        repositorio.py, relatorio.py
│   └── interface/        janela.py (Tkinter), terminal.py
└── testes/
```

| Pasta | Responsabilidade | Estado |
| --- | --- | --- |
| `clinica/modelos/` | Especialidades, prioridades, estados, senhas e especialistas | Implementado |
| `clinica/especialistas/` | Cadastro de especialistas e autenticação do administrador | Implementado |
| `clinica/filas/` | Emissão e chamada de senhas, fila FIFO para senhas normais, heap para prioritárias, encerramento diário e estimativas de espera | Implementado |
| `clinica/painel/` | Última senha chamada, consultório e espera estimada por especialidade, em dados puros (`LinhaPainel`) e em texto para o terminal | Implementado |
| `clinica/relatorio/` | Gravação das senhas, do cadastro e do administrador no SQLite (`Repositorio`) e relatório diário em texto (`Relatorio`), salvo em `relatorios/relatorio_AAAA-MM-DD.txt`; o mesmo módulo também gera as senhas do dia em CSV (`salvar_csv`) e em Excel (`salvar_excel`) | Implementado |
| `clinica/sistema.py` | Porta de entrada única: abre o dia, restaura as filas do banco, controla o acesso do administrador, grava no SQLite, gera o relatório e exporta em CSV e Excel | Implementado |
| `clinica/interface/` | Janela em Tkinter com quatro abas (`janela.py`) e menu de terminal (`terminal.py`, com consulta de relatórios por data); as duas só desenham e chamam o `Sistema` | Implementado |
| `main.py` | Ponto de entrada: cria o `Sistema` e abre a janela (ou o terminal, com `--terminal`) | Implementado |

Os módulos são importados a partir da raiz do projeto, por exemplo `from clinica.filas import GerenciadorFilas`. Os comandos devem ser executados na pasta raiz.

## Regras do projeto

- Cada especialidade pode ter até três especialistas; os consultórios vão de 1 a 12.
- Uma especialidade sem especialista cadastrado não deve emitir senhas.
- O tempo médio de atendimento usado na estimativa é de 30 minutos.
- A senha é diária: senhas não atendidas até o encerramento não passam para o dia seguinte.
- A clínica não realiza atendimentos de emergência.
- A prioridade estrita foi definida pelo grupo: senhas prioritárias são chamadas antes das normais; entre prioritárias, vale o menor código e, no empate, a ordem de chegada.
- A estimativa geral de espera considera o total de senhas aguardando, o tempo médio de atendimento de 30 minutos e a quantidade de consultórios ativos da especialidade.
- A estimativa por senha usa a mesma conta da estimativa geral: quantidade de pessoas à frente multiplicada por 30 minutos e dividida pelos consultórios ativos da especialidade, arredondada para cima. Por ser uma média, deve ser exibida como estimativa, sem garantia de tempo.
- Alguns detalhes do encerramento diário também continuam como propostas a validar.

## Como executar

Na pasta raiz do projeto:

```
python main.py              # janela (Tkinter)
python main.py --terminal   # menu de terminal
```

A janela tem quatro abas: retirar senha, painel de atendimento (atualiza sozinho a cada 2 segundos), especialista (escolhe o consultório, chama a próxima senha e finaliza o atendimento) e administrador. O terminal tem as mesmas quatro áreas em forma de menu. No primeiro acesso, o sistema pede para criar a conta do administrador; depois disso, o administrador cadastra os especialistas (no máximo três por especialidade), consulta o relatório e encerra o dia. No terminal, o administrador também pode consultar o relatório de qualquer data, informando AAAA-MM-DD, e exportar as senhas daquele dia em CSV ou Excel (`.xlsx`). Cadastro, relatório e encerramento exigem login de administrador.

O banco SQLite fica em `dados/clinica.db` e os relatórios em `relatorios/relatorio_AAAA-MM-DD.txt` (as exportações usam o mesmo nome, com `.csv` ou `.xlsx`); as duas pastas são criadas automaticamente e ficam fora do Git. Se o programa for fechado no meio do dia, as senhas voltam do banco ao reabrir. Se o dia anterior não foi encerrado, ele é fechado e o relatório é gerado ao iniciar; se a data mudar com o programa aberto, o dia anterior é encerrado e o novo começa sozinho.

Os testes automatizados rodam na raiz do projeto com `python -m unittest discover`. Os testes da janela precisam de Tkinter e de tela; sem isso, são pulados.

| Arquivo de teste | O que cobre |
| --- | --- |
| `test_fila_especialidade.py` | Heap das prioritárias, fila FIFO das normais e posição na fila |
| `test_gerenciador.py` | Erros de emissão, chamada e finalização, encerramento do dia e estimativas de espera |
| `test_cadastro_especialistas.py` | Regras do cadastro: nome, consultório e limite de 3 por especialidade |
| `test_administrador.py` | Autenticação e armazenamento da senha (salt e hash) |
| `test_painel.py` | Dados e texto do painel |
| `test_repositorio.py` e `test_relatorio.py` | Gravação no SQLite, relatório diário e exportação em CSV e Excel |
| `test_sistema.py` | Abertura do dia, restauração das filas, acesso do administrador e exportação de relatórios |
| `test_terminal.py` e `test_janela.py` | Menus do terminal (incluindo consulta e exportação de relatórios) e abas da janela |
| `test_dados_exemplo.py` | Script de dados de exemplo |

### Dados de exemplo

Para a apresentação, o banco começa vazio e cadastrar 12 especialistas à mão toda vez seria demorado. Este comando já deixa tudo pronto (12 especialistas, 3 por especialidade, nos consultórios 1 a 12, e um administrador):

```
python -m clinica.dados_exemplo
```

Pode ser executado mais de uma vez sem duplicar nada: consultórios que já têm especialista são pulados. Se já existir um administrador com outra senha, o script para com erro e não cadastra ninguém.

O usuário `admin` e a senha `admin123` servem **apenas para a demonstração**. Depois de popular, abra `python main.py` e entre na aba Administrador com esses dados.

## Grupo

- Willyan
- Luana Felix Ribeiro
- Iago de Castro Sarmento
- Bruna Stéfany
- Levi Oliveira Reis

### Contribuições

| Integrante | O que entregou |
| --- | --- |
| Willyan | Estrutura do projeto e integração (`Sistema`, terminal e janela), modelos, cadastro, filas, painel, relatório diário com SQLite e testes do `Administrador` |
| Luana | Separação entre a fila FIFO das normais e o heap das prioritárias, posição na fila e estimativa individual de espera; script de dados de exemplo; testes de `FilaEspecialidade` e `GerenciadorFilas` |
| Bruna | Testes do cadastro de especialistas |
| Levi | Consulta de relatórios de datas anteriores e exportação em CSV e Excel |
| Iago | Segurança das operações com o SQLite (em andamento) |
