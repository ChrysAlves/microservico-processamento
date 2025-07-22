#!/bin/bash

# Inicia o listener do unoconv em segundo plano para aguardar por tarefas
echo "Iniciando listener do unoconv em segundo plano..."
unoconv --listener &

# Aguarda 5 segundos para garantir que o listener esteja pronto
sleep 5

# Executa o seu script Python principal, que agora enviará tarefas para o listener
echo "Iniciando script principal do Python..."
python3 -u main.py