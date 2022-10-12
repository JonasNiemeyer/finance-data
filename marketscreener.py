import calendar
import pandas as pd
import requests
import re
from bs4 import BeautifulSoup
from finance_data.utils import HEADERS, DatasetError

class MarketscreenerReader:
    _base_url = "https://www.marketscreener.com"
    
    def __init__(self, identifier) -> None:
        params = {
            "q": identifier
        }
        html = requests.get(url=f"{self._base_url}/search/", params=params, headers=HEADERS).text
        soup = BeautifulSoup(html)
        
        try:
            company_tag = soup.find("table", {"class": "table table--small table--hover table--centered table--bordered"}).find("tbody").find_all("tr")[0].find("td").find("a")
        except AttributeError:
            raise DatasetError(f"no stock found for identifier '{identifier}'")
        
        self._company_url = f"{self._base_url}{company_tag.get('href')}"
        self._header_parsed = False

    def board_members(self) -> list:
        if not hasattr(self, "_company_soup"):
            self._get_company_information()
        
        board_members = []
        rows = self._company_soup.find("b", text="Members of the board").find_next("tr").find("td", recursive=False).find("table").find_all("tr")[1:]
        for row in rows:
            cells = row.find_all("td")
            name = cells[0].text.strip()
            title = cells[1].text.strip()
            age = cells[2].text
            if age == "-":
                age = None
            else:
                age = int(age)
            joined = cells[3].text
            if joined == "-":
                joined = None
            else:
                joined = int(joined)
            
            board_members.append(
                {
                    "name": name,
                    "title": title,
                    "age": age,
                    "joined": joined
                }
            )
        
        return board_members

    def country_information(self) -> dict:
        if not hasattr(self, "_company_soup"):
            self._get_company_information()

        header = self._company_soup.find("b", text="Sales per region")
        if header is None:
            raise DatasetError(f"no country data found for stock '{self.name}'")
        else:
            rows = header.find_next("tr").find("td", recursive=False).find("table").find_all("tr")
        
        if rows[0].find_all("td")[-1].text == "Delta":
            years = {
                index+1: int(tag.find("b").text)
                for index, tag in enumerate(rows[0].find_all("td")[1:-1])
            }
        else:
            years = {
                index+1: int(tag.find("b").text)
                for index, tag in enumerate(rows[0].find_all("td")[1:])
            }
        data = {}
        for year in sorted(years.values(), reverse=True):
            data[year] = {}

        for row in rows[1:-1]:
            cells = row.find_all("td")
            name = cells[0].text.title()
            for index, cell in enumerate(cells[1:-1:2]):
                data[years[index+1]][name] = float(cell.text.replace(" ", "")) * 1e6 if cell.text != "-" else None
        
        return data

    def industry_information(self) -> list:
        if not hasattr(self, "_company_soup"):
            self._get_company_information()

        industries = []
        rows = self._company_soup.find("b", text="Sector").find_next("div").find("table").find_all("tr")
        for row in rows:
            industry = row.find_all("td")[-1].find("a").text
            industries.append(industry)
        
        self._industry = industries[-1]
        
        return industries
    
    def managers(self) -> list:
        if not hasattr(self, "_company_soup"):
            self._get_company_information()
        
        managers = []
        rows = self._company_soup.find("b", text="Managers").find_next("tr").find("td", recursive=False).find("table").find_all("tr")[1:]
        for row in rows:
            cells = row.find_all("td")
            name = cells[0].text.strip()
            title = cells[1].text.strip()
            age = cells[2].text
            if age == "-":
                age = None
            else:
                age = int(age)
            joined = cells[3].text
            if joined == "-":
                joined = None
            else:
                joined = int(joined)
            
            managers.append(
                {
                    "name": name,
                    "title": title,
                    "age": age,
                    "joined": joined
                }
            )
        
        return managers

    def news(
        self,
        news_type="all",
        start=pd.to_datetime("today").date().isoformat(),
        timestamps=False
    ) -> list:
        news_types = {
            "most_relevant": ("news-quality", "Most relevant news about"),
            "all": ("news-history", "All news about"),
            "analysts": ("news-broker-research", "Analyst Recommendations on"),
            "other_languages": ("news-other-languages", "News in other languages on"),
            "press_releases": ("news-communiques", "Communiqués de presse de la société"),
            "official_publications": ("news-publications", "Official Publications"),
            "sector": ("news-sector", "Sector news")
        }
        if news_type not in news_types:
            raise ValueError(f"news_type has be one of the following: {tuple(news_types.keys())}")
        
        if isinstance(start, str):
            start = pd.to_datetime(start).timestamp()
        elif not isinstance(start, (int, float)):
            raise ValueError("start parameter has to be of type str, float or int")        
        
        source = news_types[news_type][0]
        if news_type == "sector":
            if not hasattr(self, "_industry"):
                self.industry_information()
            header = f"{news_types[news_type][1]} {self._industry}"
        elif news_type == "official_publications":
            header = news_types[news_type][1]
        else:
            header = f"{news_types[news_type][1]} {self.name()}"
        
        articles = []
        start_reached = False
        page_counter = 0
        
        while start_reached is False:
            page_counter+=1
            url = f"{self._company_url}/{source}/fpage={page_counter}"
            html = requests.get(url=url, headers=HEADERS).text
            soup = BeautifulSoup(html, "lxml")
            
            rows = soup.find("b", text=header).find_next("tr").find("td", recursive=False).find("table").find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                date = cells[0].text
                if ":" in date:
                    date =  pd.to_datetime("today")
                elif "/" in date:
                    current_year = pd.to_datetime("today").year
                    date =  pd.to_datetime(f"{date}/{current_year}")
                else:
                    date = pd.to_datetime(f"{date}-01-01")

                if date.timestamp() < start:
                    start_reached = True
                    break
                
                if timestamps:
                    date = int(date.timestamp())
                else:
                    date = date.date().isoformat()
                
                url = cells[1].find("a").get("href")
                url = f"{self._base_url}{url}"
                title = cells[1].find("a").text
                if cells[1].find("a").find("b") is not None:
                    title = title.replace(" :", ":")
                news_source = cells[2].find("div")
                if news_source is None:
                    news_source = None
                    news_source_abbr = None
                else:
                    news_source_abbr = news_source.text
                    news_source = news_source.get("title").replace("©", "")
                
                articles.append(
                    {
                        "title": title,
                        "date": date,
                        "source": {
                            "name": news_source,
                            "abbreviation": news_source_abbr
                        },
                        "url": url
                    }
                )
            
            
            pages_nav = soup.find("span", {"class": "nPageTable"})
            if (pages_nav is None) or (pages_nav.find("a", {"class": "nPageEndTab"}) is None):
                start_reached = True
            
        return articles

    def segment_information(self) -> dict:
        if not hasattr(self, "_company_soup"):
            self._get_company_information()
        
        header = self._company_soup.find("b", text="Sales per Business")
        if header is None:
            raise DatasetError(f"no segment data found for stock '{self.name}'")
        else:
            rows = header.find_next("tr").find("td", recursive=False).find("table").find_all("tr")
        
        if rows[0].find_all("td")[-1].text == "Delta":
            years = {
                index+1: int(tag.find("b").text)
                for index, tag in enumerate(rows[0].find_all("td")[1:-1])
            }
        else:
            years = {
                index+1: int(tag.find("b").text)
                for index, tag in enumerate(rows[0].find_all("td")[1:])
            }
        data = {}
        for year in sorted(years.values(), reverse=True):
            data[year] = {}

        for row in rows[1:-1]:
            cells = row.find_all("td")
            name = cells[0].text
            for index, cell in enumerate(cells[1:-1:2]):
                data[years[index+1]][name] = float(cell.text.replace(" ", "")) * 1e6 if cell.text != "-" else None
        
        return data

    def shareholders(self) -> list:
        if not hasattr(self, "_company_soup"):
            self._get_company_information()
        
        shareholders = []
        rows = self._company_soup.find("b", text="Shareholders").find_next("tr").find("td", recursive=False).find("table").find_all("tr")[1:]
        for row in rows:
            cells = row.find_all("td")
            company = cells[0].text.strip()
            shares = int(cells[1].text.replace(",", ""))
            percentage = round(float(cells[2].text.replace("%", ""))/100, 4)
            
            shareholders.append(
                {
                    "company": company,
                    "shares": shares,
                    "percentage": percentage
                }
            )
        
        return shareholders

    def _get_company_information(self) -> None:
        url = f"{self._company_url}/company/"
        html = requests.get(url=url, headers=HEADERS).text
        self._company_soup = BeautifulSoup(html)

    def _get_financial_information(self) -> None:
        url = f"{self._company_url}/financials/"
        html = requests.get(url=url, headers=HEADERS).text
        self._financial_soup = BeautifulSoup(html)
    
    def _parse_header(self) -> None:
        if self._header_parsed:
            return
        if hasattr(self, "_financial_soup"):
            soup = self._financial_soup
        elif hasattr(self, "_company_soup"):
            soup = self._company_soup
        else:
            self._get_financial_information()
            soup = self._financial_soup
        
        ticker, isin = soup.find("div", {"class": "bc_pos"}).find("span", {"class": "bc_add"}).find_all("span")
        self._ticker = ticker.text.strip()
        self._isin = isin.text.strip()
        
        self._name = re.findall("(.+)\(.+\)", soup.find("h1").parent.text.strip())[0].strip()
        
        price_tag = soup.find("span", {"class": "last variation--no-bg txt-bold"})
        self._price = float(price_tag.text)
        self._currency = price_tag.find_next("td").text.strip()
        
        self._header_parsed = True