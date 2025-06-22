Uma expressão cron é um formato de string utilizado para especificar agendamentos de tarefas de forma muito flexível. É amplamente usado em sistemas Unix/Linux e em muitas aplicações para definir quando uma tarefa deve ser executada.

## Formato de uma expressão cron

Uma expressão cron tradicional tem cinco ou seis campos, separados por espaços:

```
┌───────────── minutos (0-59)
│ ┌─────────── horas (0-23)
│ │ ┌───────── dia do mês (1-31)
│ │ │ ┌─────── mês (1-12 ou JAN-DEZ)
│ │ │ │ ┌───── dia da semana (0-6 ou DOM-SAB)
│ │ │ │ │
* * * * *
```

Em algumas implementações, há um sexto campo para segundos (0-59) no início da expressão.

## Operadores comuns em expressões cron

- **Asterisco (`*`)**: Representa "qualquer valor" ou "todos"
- **Vírgula (`,`)**: Para listar múltiplos valores (ex: 1,5,10)
- **Hífen (`-`)**: Para especificar um intervalo (ex: 1-5, significa 1,2,3,4,5)
- **Barra (`/`)**: Para especificar incrementos (ex: */5 nos minutos significa a cada 5 minutos)

## Exemplos práticos para sua coluna `agendamento_cron`

1. **Segunda a sexta, das 9h às 17h**:
   ```
   0 9-17 * * 1-5
   ```

2. **Todos os dias às 10h, 14h e 18h**:
   ```
   0 10,14,18 * * *
   ```

3. **Apenas aos sábados e domingos, das 10h às 20h, a cada 30 minutos**:
   ```
   */30 10-20 * * 0,6
   ```

4. **Dias úteis das 8h às 12h e das 14h às 18h**:
   ```
   0 8-12,14-18 * * 1-5
   ```

A coluna `agendamento_cron` na tabela `campanhas` permite armazenar esses padrões de agendamento de forma compacta, possibilitando grande flexibilidade na definição dos dias e horários de funcionamento das campanhas.