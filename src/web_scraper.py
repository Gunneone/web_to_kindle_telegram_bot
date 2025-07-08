import requests
from bs4 import BeautifulSoup
from datetime import datetime

class Article:
    def __init__(self, url, title, author, published_at, content):
        self.URL = url
        self.Title = title
        self.Author = author
        self.Published_At = published_at
        self.Content = content

    def __getitem__(self, key):
        return getattr(self, key)
    def __setitem__(self, key, value):
        return setattr(self, key, value)
        
def get_substack_content(url: str):
    """
    Extracts the main article content from a Substack blog post URL.

    Args:
        url (str): The URL of the Substack blog post

    Returns:
        str: HTML content of the main article

    Raises:
        Exception: If the URL is invalid or content cannot be retrieved
    """
    try:
        # Send HTTP GET request
        response = requests.get(url)
        response.raise_for_status()

        # Parse HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the main article content by looking for the article class
        article_content = soup.find('article')

        

        if article_content:

            # extract author
            author_element = soup.find('div', class_='profile-hover-card-target')
            author = author_element.find('a').text.strip() if author_element else "Unknown Author"

            # extract title which is the first h1, that is not in a .pc-display-flex element
            h1_elements = soup.find_all('h1')
            title = None
            for h1 in h1_elements:
                if not h1.find_parent(class_='pc-display-flex'):
                    title = h1.text.strip()

                    # Create and insert author heading and horizontal line after title
                    author_heading = soup.new_tag('h4')
                    author_heading.string = f"By {author}"
                    horizontal_line = soup.new_tag('hr')
                    horizontal_line['style'] = 'border-top: 1px solid #ccc; margin: 20px 0;'

                    h1.insert_after(horizontal_line)
                    h1.insert_after(author_heading)
                    break
            if not title:
                title = "Unknown Title"

            # Remove share buttons, like buttons etc
            for element in article_content.select(
                    '.pc-display-flex, .button-wrapper, .modal, .popup'):
                element.decompose()

            safe_title = title.lower().replace(' ', '-')[:70]
            # first store the html file to /html/*current timestamp* for debugging purposes
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(f"./html/{safe_title}-{timestamp}.html", "w") as f:
                f.write(str(article_content))

            # create Article object with article_content, title and author
            article = Article(
                url=url,
                title=title,
                author=author,
                published_at=datetime.now().isoformat(),
                content=str(article_content)
            )

            return article
        else:
            raise Exception("Could not find article content")

    except requests.RequestException as e:
        raise Exception(f"Error fetching content: {str(e)}")
    except Exception as e:
        # print whole stack trace
        print(e)
        raise Exception(f"Error processing content: {str(e)}")
