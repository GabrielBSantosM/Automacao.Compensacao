import os
import re
import pdfplumber
import pandas as pd
import re

pattern = re.compile(
    r"(?P<codigo>\d+)\s+(?P<tipo>Fatura|Invoice|Debit Note)(?:\s+\d+)?\s+(?P<data>\d{2}\.\d{2}\.\d{4})\s+BRL\s+([-\d.,]+)(?:\s+BRL\s+([-\d.,]+))?"
)


def processar_pdf_compensacao(caminho_pdf):
    faturas, debitos = [], []
    with pdfplumber.open(caminho_pdf) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for match in pattern.finditer(text):
                data = match.groupdict()
                codigo = data["codigo"]
                tipo = data["tipo"]
                data_fatura = data["data"]
                compensado_raw = match.group(5) if match.group(5) else match.group(4)
                compensado = compensado_raw.replace(".", "").replace(",", ".")
                registro = {
                    "fatura": codigo,
                    "pagador": "HOTELBEDS",
                    "data_vencimento": pd.to_datetime(data_fatura, format="%d.%m.%Y"),
                    "valor_boleto": abs(float(compensado))
                }
                if tipo in ["Fatura", "Invoice"]:
                    registro["tipo"] = "Fatura"
                    faturas.append(registro)
                else:
                    registro["tipo"] = "Desconto"
                    registro["valor_desconto"] = abs(float(compensado))
                    debitos.append(registro)

    if not faturas and not debitos:
        print(f"Aviso: Nenhum dado extraído de '{caminho_pdf}'.")
        return pd.DataFrame(columns=[
            "fatura", "pagador", "data_vencimento", "data_pagamento",
            "valor_boleto", "valor_desconto", "valor_pago"
        ])


    faturas.sort(key=lambda x: -x["valor_boleto"])
    debitos.sort(key=lambda x: -x["valor_desconto"])

    resultado = []
    i = 0
    for fatura in faturas:
        if i < len(debitos):
            desconto = debitos[i]["valor_desconto"]
            fatura["valor_desconto"] = desconto
            fatura["valor_pago"] = fatura["valor_boleto"] - desconto
            resultado.append(fatura)
            i += 1
        else:
            fatura["valor_desconto"] = 0.0
            fatura["valor_pago"] = fatura["valor_boleto"]
            resultado.append(fatura)

    while i < len(debitos):
        maior_fatura = max(resultado, key=lambda x: x["valor_boleto"])
        desconto = debitos[i]["valor_desconto"]
        maior_fatura["valor_desconto"] += desconto
        maior_fatura["valor_pago"] = maior_fatura["valor_boleto"] - maior_fatura["valor_desconto"]
        i += 1

    df = pd.DataFrame(resultado)
    df["data_pagamento"] = df["data_vencimento"]
    df = df[[
        "fatura", "pagador", "data_vencimento", "data_pagamento", "valor_boleto", "valor_pago", "valor_desconto"
    ]]
    return df

# Criar pasta de saída se não existir
os.makedirs("saida", exist_ok=True)

# Percorrer PDFs da pasta entrada
for nome_arquivo in os.listdir("entrada"):
    if nome_arquivo.lower().endswith(".pdf"):
        caminho = os.path.join("entrada", nome_arquivo)
        nome_base = os.path.splitext(nome_arquivo)[0].replace(" ", "_")
        print(f"Processando: {nome_arquivo}")
        df_final = processar_pdf_compensacao(caminho)
        df_final.to_excel(f"saida/{nome_base} - OK.xlsx", index=False)

print("\n✅ Todos os PDFs foram processados e salvos na pasta 'saida'.")