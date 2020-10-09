from io import StringIO, BytesIO
import requests
import PyPDF2


def read_pdf(url):
    text = StringIO()
    response = requests.get(url)
    pdf = PyPDF2.PdfFileReader(BytesIO(response.content))
    for page_number in range(pdf.numPages):
        page = pdf.getPage(page_number)
        result = page.extractText()
        text.write(result)
    return text.getvalue()
