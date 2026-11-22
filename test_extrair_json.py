import json
from ia import extrair_json

# JSON de exemplo - simulando o que o IA retorna (truncado)
test_data = {
    "candidates": [
        {
            "indice_curriculo": 1,
            "identificacao_candidato": {
                "nome": "LUCAS MORAES",
                "cargo_declarado": "Desenvolvedor Backend Pleno (Java)",
                "tempo_experiencia_estimado": "3 anos e meio",
                "contato": {
                    "email": "lucas.moraes@email.com",
                    "telefone": "",
                    "localizacao": "Jaguariúna, SP"
                }
            },
            "avaliacao_vaga": {
                "score_geral": 78,
                "decisao_triagem": "Priorizar revisão humana",
                "justificativa_coerencia": "Experiencia direta com Java backend, Spring Boot, MySQL"
            }
        }
    ]
}

# Criar JSON completo
json_completo = json.dumps(test_data)

# Criar JSON truncado (remover o final)
json_truncado = json_completo[:-60]

print("=== Teste de JSON truncado ===")
print("JSON truncado (tamanho original: %d, truncado em: %d):" % (len(json_completo), len(json_truncado)))
print("JSON truncado (primeiros 150 chars):", json_truncado[:150])

try:
    resultado = extrair_json(json_truncado)
    print("Teste 1 - Sucesso! JSON truncado recuperado:")
    print("  - Número de candidatos:", len(resultado.get("candidates", [])))
except Exception as e:
    print("Teste 1 erro:", e)

# Testar JSON completo
print()
print("=== Teste de JSON válido ===")
try:
    resultado = extrair_json(json_completo)
    print("Teste 2 - Sucesso:", json.dumps(resultado, ensure_ascii=False)[:200])
except Exception as e:
    print("Teste 2 erro:", e)
