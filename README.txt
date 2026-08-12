Rebrand: DataCo  ->  Meridian Retail Group
==========================================

WHAT CHANGED
------------
- New logo, drawn as SVG so it stays sharp at any size and on any
  screen: assets/logo.svg
- Sidebar now shows the logo with MERIDIAN / RETAIL GROUP under it
- Browser tab title
- The big title on the Home page
- Page descriptions on Executive, Customers and World map
- The chatbot's own wording: it now says it covers "Meridian data"
- The startup line in the terminal


ONE LINE WAS DELIBERATELY LEFT ALONE
------------------------------------
At the bottom of the sidebar:

    Data: Constante, Silva & Pereira (2019),
    DataCo Smart Supply Chain, Mendeley Data V5 - CC BY 4.0

That "DataCo Smart Supply Chain" is NOT the company name - it is the
published title of the dataset you are using, by those three authors.
Renaming it would be citing a source that does not exist, and the CC BY
4.0 licence you are using the data under requires the original title
and authors to be credited exactly.

Meridian Retail Group is the fictional company the analysis is about.
DataCo Smart Supply Chain is the real dataset it is built from. Both
statements are true at the same time, and keeping them apart is what
makes the work honest.

If a committee member asks about it, that is a good answer to have.


FILES
-----
assets/logo.svg      (new)
assets/style.css     (replaced - logo styling)
app.py               (replaced - sidebar, title)
agent.py             (replaced - chatbot wording)
geo.py               (replaced - one comment)
check_setup.py       (replaced - one message)
pages/home.py        (replaced)
pages/map.py         (replaced)
pages/customers.py   (replaced)
pages/executive.py   (replaced)


HOW TO INSTALL
--------------
1. Unzip.
2. Select everything inside "meridian-rebrand" (Ctrl+A), copy.
3. Paste into your project folder, choose "Replace".
4. Close START.bat, open it again. Press Ctrl+F5 in the browser.

No database rebuild needed.
