from sqlalchemy import create_engine, text
import urllib

password = urllib.parse.quote_plus("Mx^aRU9x{KGk")  # URL encode special chars

uri = f"mysql+pymysql://finelan1_2020:{password}@box2329.bluehost.com:3306/finelan1_new2020"

# uri = "mysql+pymysql://finelan1_2020:Mx^aRU9x{KGk@box2329.bluehost.com:3306/finelan1_new2020"
engine = create_engine(uri)

try:
    with engine.connect() as conn:
        print("CONNECTED:")
        # result = conn.execute(text("""
        # SELECT *
        # FROM product p
        # JOIN stock s
        #     ON p.brand_part_number = s.brand_part_no
        # """))

        # rows = result.fetchall()
        # print(len(rows))
        # for row in rows[:10]:
        #     print(row)
        # result = conn.execute(text("DESCRIBE stock"))
        # rows = result.fetchall()
        # columns = [row[0] for row in result.fetchall()]
        # print("Product Columns:", columns)
        # print("Total Rows:", len(rows))
        # for row in rows:
        #     print(row)
except Exception as e:
    print("FAILED:", e)
