# Identificação do Empreendimento

<!-- IN 37 Anexo VII, item I: razão social, nome fantasia, CNPJ/IE, endereço completo da unidade,
     endereço para correspondência, responsável + telefone, e-mail. -->

**Razão Social:** {{empresa.razao_social}}

**Nome Fantasia:** {{empresa.nome_fantasia}}

**CNPJ:** {{empresa.cnpj}}

**Inscrição Estadual:** {{empresa.inscricao_estadual}}

**Endereço Completo da Unidade a ser Licenciada**

<!-- Padrão do modelo: o empreendimento tem várias unidades; citar o endereço da unidade principal (ETA),
     com rua e cruzamento de referência, e remeter às coordenadas do item 3.3. Fotos da via de acesso. -->
O empreendimento é composto por múltiplas unidades distribuídas no território do município de {{municipio}}/{{uf}}, não se restringindo a um único endereço. A unidade principal do sistema está localizada em {{endereco_unidade_principal}}. As demais unidades do sistema estão distribuídas conforme detalhado no item 3 (Caracterização da Área) deste memorial, com as respectivas coordenadas geográficas e UTM.

**Endereço para Correspondência:** {{empresa.endereco_correspondencia}}

**Responsáveis envolvidos no projeto:**

::: quadro {#qua:equipe fonte="{{empresa.sigla}}, {{ano}}."} Relação dos envolvidos no projeto – equipe {{empresa.sigla}}
| Nome | Função / Vínculo | Registro profissional | Telefone |
|---|---|---|---|
| {{empresa.envolvidos.0.nome}} | {{empresa.envolvidos.0.funcao}} | {{empresa.envolvidos.0.registro}} | {{empresa.envolvidos.0.telefone}} |
| {{empresa.envolvidos.1.nome}} | {{empresa.envolvidos.1.funcao}} | {{empresa.envolvidos.1.registro}} | {{empresa.envolvidos.1.telefone}} |
| {{empresa.envolvidos.2.nome}} | {{empresa.envolvidos.2.funcao}} | {{empresa.envolvidos.2.registro}} | {{empresa.envolvidos.2.telefone}} |
:::
