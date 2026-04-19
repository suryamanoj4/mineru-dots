"""
get cov
"""
from bs4 import BeautifulSoup
import shutil
def get_covrage():
    """get covrage"""
    # Read web page content
    html_content = open("htmlcov/index.html", "r", encoding="utf-8").read()
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the span tag containing "pc_cov"
    pc_cov_span = soup.find('span', class_='pc_cov')

    # Extract percentage value
    percentage_value = pc_cov_span.text.strip()
    percentage_float = float(percentage_value.rstrip('%'))
    print ("percentage_float:", percentage_float)
    assert percentage_float >= 0.2

if __name__ == '__main__':
    get_covrage()