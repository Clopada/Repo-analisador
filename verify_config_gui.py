import os, tempfile, shutil
from pathlib import Path
import sys
sys.path.insert(0, '/home/clop/Documentos/Projeto automação/Automação')
os.chdir('/home/clop/Documentos/Projeto automação/Automação')

# Backup the .env
shutil.copy('Automação/.env', 'Automação/.env.bak_test')

# Simulate saving new test values via ConfigTabTeste
# We'll just directly write the new values for demonstration
novo_env = {
    'EMAIL': 'seu-email@gmail.com',
    'DESTINATARIO': 'destino@empresa.com.br',
    'NVIDIA_API_KEY': '',
    'NVIDIA_MODEL': 'nvidia/nemotron-3-super-120b-a12b',
    'NVIDIA_BASE_URL': 'https://integrate.api.nvidia.com/v1',
    'LIMITE_LOTE': '5',
    'INTERVALO_MINUTOS': '5',
    'INTERVALO_SEGUNDOS': '5',
}

# Read existing .env lines, update if needed
linhas = []
with open('Automação/.env', 'r', encoding='utf-8') as f:
    for linha in f:
        linha = linha.rstrip('\n')
        if '=' in linha and not linha.lstrip().startswith('#'):
            chave = linha.split('=', 1)[0].strip()
            if chave in novo_env:
                valor = novo_env[chave]
                # Use double quotes as in config_gui's _formatar_env
                linha = f'{chave}="{valor}"'
        linhas.append(linha)

# Append any new keys not present
chaves_existentes = {l.split('=',1)[0].strip() for l in linhas if '=' in l and not l.lstrip().startswith('#')}
for k, v in novo_env.items():
    if k not in chaves_existentes:
        linhas.append(f'{k}="{v}"')

with open('Automação/.env', 'w', encoding='utf-8') as f:
    f.write('\n'.join(linhas) + '\n')

# Now load config module to see values
import importlib
import config
importlib.reload(config)

print('LIMITE_LOTE =', config.LIMITE_LOTE)
print('INTERVALO_MINUTOS =', config.INTERVALO_MINUTOS)
print('INTERVALO_SEGUNDOS =', config.INTERVALO_SEGUNDOS)

# Restore original .env later
# shutil.copy('Automação/.env.bak_test', 'Automação/.env')
