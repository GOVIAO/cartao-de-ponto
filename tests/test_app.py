from backend.app import parse_payroll_page, parse_timecard_page, rows_for_export

def test_timecard_sipon():
    text = """Dia Semana Jornada Entrada Saida Ocorrencia Qtde
1 - DOM 08:00
2 - SEG 08:00 09:03 14:05 HE-BCO DE HORAS 00:13
15:12 18:36 HE-REMUNERADA 00:13"""
    value = parse_timecard_page(text, 1)
    assert value["days"][0]["punches"] == []
    assert [p["time_hhmm"] for p in value["days"][1]["punches"]] == ["09:03", "14:05", "15:12", "18:36"]

def test_payroll_fields_and_bases():
    text = """Período : 10/2019
Cod. Descrição Unidade Proventos Descontos
0105 Dias Trabalhados 30,00 1.678,61
2100 DSR sobre Variaveis 26,77
Total 1.967,07 859,46
Líqüido 1.107,61
Base I.N.S.S. : 1.967,07 F.G.T.S. do Mês : 157,37
Base I.R.R.F. : 1.790,04 Base I.R.R.F. 13o.:
Dep. I.R.R.F. : 0,00 Base FGTS: 1.967,07"""
    value = parse_payroll_page(text, 1)
    assert value["month"] == "10"
    assert value["year"] == "2019"
    assert value["fields"][0] == {"code":"0105","label":"Dias Trabalhados","reference":"30,00","value":"1.678,61"}
    assert any(x["label"] == "Base INSS" and x["value"] == "1.967,07" for x in value["bases"])
    assert any(x["label"] == "FGTS" and x["value"] == "157,37" for x in value["bases"])

def test_export_holerite_columns():
    value={"pages":[{"page":1,"year":"2020","month":"01","fields":[{"code":"1","label":"Salário","reference":"","value":"1.000,00"}],"bases":[]}]}
    headers, rows, warnings = rows_for_export(value,"holerite")
    assert headers == ["Pág.","Mês","Ano","Salário"]
    assert rows == [[1,"01","2020","1.000,00"]]
