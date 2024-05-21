import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from fpdf import FPDF
import streamlit as st
import tempfile

# Definir valores fixos
VALOR_KWH_CEMIG = 0.956
DESCONTO = 20
VALOR_KWH_FATURADO = 0.7648

# Função para processar os dados
def process_data(df):
    df['Período'] = pd.to_datetime(df['Período'], format='%m/%Y')
    last_month = df['Período'].max()
    df_last_month = df[df['Período'] == last_month]
    
    cols_to_drop = ["Quantidade Saldo a Expirar", "Período Saldo a Expirar", "Quota", 
                    "Posto Horário", "Saldo Anterior", "Saldo Expirado", "Transferido", "Geração"]
    df_last_month = df_last_month.drop(columns=cols_to_drop)
    
  #  df_last_month = df_last_month.iloc[[2, 4]]
    df_last_month = df_last_month[df_last_month['Compensação'] != 0]

    df_last_month.loc[df_last_month['Instalação'] == 3013110767, 'Modalidade'] = 'GBBH - Lj 02'
    df_last_month.loc[df_last_month['Instalação'] == 3013096188, 'Modalidade'] = 'GBBH - Lj 01'
    
    df_last_month['Saldo Atual'] = df_last_month['Saldo Atual'].round(2)
    df_last_month['Período'] = df_last_month['Período'].dt.strftime('%m/%y')
    
    # Atualizar RECEBIDO com o valor da primeira linha da coluna "Transferido"
    RECEBIDO = df['Transferido'].iloc[0]

    
   # RECEBIDO = df_last_month['Recebimento'].sum()
    VALOR_A_PAGAR = (RECEBIDO * VALOR_KWH_FATURADO).round(2)
    
    return df_last_month, RECEBIDO, VALOR_A_PAGAR

# Função para calcular consumo e energia injetada por mês
def calculate_consumption_generation(df):
    df['Período'] = pd.to_datetime(df['Período'], format='%m/%Y')
    
    monthly_data = df.groupby('Período').agg({'Consumo': 'sum', 'Geração': lambda x: x[x != 0].sum()})
    
    months_map = {
        'Jan': 'Jan/', 'Feb': 'Fev/', 'Mar': 'Mar/', 'Apr': 'Abr/', 'May': 'Mai/', 'Jun': 'Jun/',
        'Jul': 'Jul/', 'Aug': 'Ago/', 'Sep': 'Set/', 'Oct': 'Out/', 'Nov': 'Nov/', 'Dec': 'Dez/'
    }
    monthly_data.index = (monthly_data.index - pd.DateOffset(months=1)).strftime('%b-%y')
    monthly_data.index = monthly_data.index.map(lambda x: x.capitalize())
    monthly_data.index = monthly_data.index.map(lambda x: months_map[x.split('-')[0]] + x.split('-')[1])
    
    monthly_data = monthly_data.rename(columns={'Consumo': 'Consumo [kWh]', 'Geração': 'Energia Injetada [kWh]'})
    
    average_consumption = monthly_data['Consumo [kWh]'].mean()
    average_generation = monthly_data['Energia Injetada [kWh]'].mean()
    
    monthly_data.loc['Média'] = [int(average_consumption), int(average_generation)]
    # Supondo que monthly_data seja o DataFrame que você deseja exibir na imagem
    monthly_data.reset_index(inplace=True)

    return monthly_data

# Função para gerar a imagem com os dados processados
def generate_image(preprocessed_df, monthly_data, RECEBIDO, VALOR_A_PAGAR, ultimo_periodo, economia):
    img = Image.open('boleto_padrao.png')
    draw = ImageDraw.Draw(img)
    
    recebido_text = str(int(RECEBIDO))
    valor_a_pagar_text = str(VALOR_A_PAGAR)
   
    # Create an input field for the customer name
    cliente_text = st.text_input("Digite o nome do cliente:", placeholder="Gracie Barra BH")

   # cliente_text = "Gracie Barra BH"
    mes_text = str(ultimo_periodo)
    vencimento_text = "26/" + ultimo_periodo
    
    # Calculando o desconto
    desconto = VALOR_KWH_CEMIG - VALOR_KWH_FATURADO

    # Somando a coluna "Energia Injetada [kWh]" em todas as linhas, exceto a última
    energia_total = monthly_data.iloc[:-1]["Energia Injetada [kWh]"].sum()

    # Calculando quanto o cliente economizou
    economia = (energia_total * desconto).round(2)

    economia_formatada = "{:.2f}".format(economia)
    economia_text = economia_formatada.replace('.', ',')
    
    font_size = 38
    font_size2 = 25
    font = ImageFont.truetype("arialbd.ttf", font_size)
    font2 = ImageFont.truetype("arial.ttf", font_size2)
    
    draw.text((910, 1173), recebido_text, fill="black", font=font)
    draw.text((940, 1412), valor_a_pagar_text, fill="black", font=font)
    draw.text((297, 636), cliente_text, fill="black", font=font2)
    draw.text((440, 672), mes_text, fill="black", font=font2)
    draw.text((360, 707), vencimento_text, fill="black", font=font2)
    draw.text((1060, 2212), economia_text, fill="black", font=font)
    
    # Selecionar apenas os últimos 11 meses com registro
    monthly_data01 = monthly_data.iloc[-12:]

    dataframe_position = (255, 1130)
    font_size_df = 14.5
    font_df = ImageFont.truetype("arial.ttf", font_size_df)
    font_bold_df = ImageFont.truetype("arialbd.ttf", font_size_df)
    color_light_gray = "#F0F0F0"
    color_dark_gray = "#D3D3D3"
    cell_width_df = 160
    cell_height_df = 28
    
    columns = list(monthly_data01.columns)
    for j, column_name in enumerate(columns):
        text_width = draw.textlength(str(column_name), font=font_bold_df)
        text_position_x = dataframe_position[0] + j * cell_width_df + (cell_width_df - text_width) // 2
        draw.rectangle(
            [(dataframe_position[0] + j * cell_width_df, dataframe_position[1]),
             (dataframe_position[0] + (j + 1) * cell_width_df, dataframe_position[1] + cell_height_df)],
            fill=color_dark_gray,
            outline="black"
        )
        draw.text((text_position_x, dataframe_position[1] + 2), str(column_name), fill="black", font=font_bold_df)
    
    for i, (_, row) in enumerate(monthly_data01.iterrows()):
        for j, cell_value in enumerate(row):
            background_color_df = color_dark_gray if i == len(monthly_data01) - 1 else color_light_gray
            draw.rectangle(
                [(dataframe_position[0] + j * cell_width_df, dataframe_position[1] + (i + 1) * cell_height_df),
                 (dataframe_position[0] + (j + 1) * cell_width_df, dataframe_position[1] + (i + 2) * cell_height_df)],
                fill=background_color_df,
                outline="black"
            )
            cell_text = str(cell_value)
            if i == len(monthly_data01) - 1:
                cell_text = cell_text.upper() if columns[j] == "Período" else cell_text
                text_width = draw.textlength(cell_text, font=font_bold_df)
                text_font = font_bold_df
            else:
                text_width = draw.textlength(cell_text, font=font_df)
                text_font = font_df
            text_height = text_font.size
            text_position = (
                dataframe_position[0] + j * cell_width_df + (cell_width_df - text_width) // 2,
                dataframe_position[1] + (i + 1) * cell_height_df + (cell_height_df - text_height) // 2
            )
            draw.text(text_position, cell_text, fill="black", font=text_font)
    
    dataframe_position = (220, 868)
    font_size_df = 18
    font_df = ImageFont.truetype("arial.ttf", font_size_df)
    font_bold_df = ImageFont.truetype("arialbd.ttf", font_size_df)
    cell_width_df = 180
    cell_height_df = 46
    
    columns = list(preprocessed_df.columns)
    for j, column_name in enumerate(columns):
        text_width = draw.textlength(str(column_name), font=font_bold_df)
        text_position_x = dataframe_position[0] + j * cell_width_df + (cell_width_df - text_width) // 2
        draw.rectangle(
            [(dataframe_position[0] + j * cell_width_df, dataframe_position[1]),
             (dataframe_position[0] + (j + 1) * cell_width_df, dataframe_position[1] + cell_height_df)],
            fill=color_dark_gray,
            outline="black"
        )
        draw.text((text_position_x, dataframe_position[1] + 2), str(column_name), fill="black", font=font_bold_df)
    
    for i, (_, row) in enumerate(preprocessed_df.iterrows()):
        for j, cell_value in enumerate(row):
            background_color_df = color_light_gray
            draw.rectangle(
                [(dataframe_position[0] + j * cell_width_df, dataframe_position[1] + (i + 1) * cell_height_df),
                 (dataframe_position[0] + (j + 1) * cell_width_df, dataframe_position[1] + (i + 2) * cell_height_df)],
                fill=background_color_df,
                outline="black"
            )
            cell_text = str(cell_value)
            text_width = draw.textlength(cell_text, font=font_df)
            text_font = font_df
            text_height = text_font.size
            text_position = (
                dataframe_position[0] + j * cell_width_df + (cell_width_df - text_width) // 2,
                dataframe_position[1] + (i + 1) * cell_height_df + (cell_height_df - text_height) // 2
            )
            draw.text(text_position, cell_text, fill="black", font=text_font)
    
    return img

# Função para gerar PDF a partir da imagem

def generate_pdf(image):
    # Definir dimensões do PDF (8.28 x 11.69 inches em pontos)
    pdf = FPDF(unit='pt', format=[598.56, 845.28])
    pdf.add_page()
    
    # Salvar a imagem temporariamente em um arquivo
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
        image.save(tmpfile, format='PNG')
        tmpfile_path = tmpfile.name

    # Adicionar a imagem ao PDF
    pdf.image(tmpfile_path, x=0, y=0, w=598.56, h=845.28)

    # Salvar o PDF em um objeto BytesIO
    pdf_output = BytesIO()
    pdf.output(dest='S').encode('latin1')
    pdf_output.write(pdf.output(dest='S').encode('latin1'))
    pdf_output.seek(0)

    return pdf_output

# Configuração do Streamlit
st.title('Processamento de Dados Energéticos')



uploaded_file = st.file_uploader("Faça o upload do arquivo XLSX", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df_last_month, RECEBIDO, VALOR_A_PAGAR = process_data(df)
    monthly_data = calculate_consumption_generation(df)
    economia = RECEBIDO * (VALOR_KWH_CEMIG - VALOR_KWH_FATURADO)
    ultimo_periodo = df_last_month['Período'].max()
    img = generate_image(df_last_month, monthly_data, RECEBIDO, VALOR_A_PAGAR, ultimo_periodo, economia)
    # Gerar o PDF e exibir o link para download
   # pdf_output = generate_pdf(img)
   # st.download_button(label="Baixar PDF", data=pdf_output, file_name="boleto.pdf", mime="application/pdf")
    #Create buttons for image and PDF generation
    generate_image_button = st.button("Gerar Imagem")
    generate_pdf_button = st.button("Gerar PDF")
   
   
    if generate_image_button:
        st.image(img, caption='Imagem Gerada', use_column_width=True)
    if generate_pdf_button:
      # Gerar o PDF e exibir o link para download
       pdf_output = generate_pdf(img)
       st.download_button(label="Baixar PDF", data=pdf_output, file_name="boleto.pdf", mime="application/pdf")
