"""Original IELTS practice question seed (PRD FR-08, reconciliation R12).

All prompts are original content written for AI Writing Coach; no Cambridge
or other third-party material is reproduced. Task 1 Academic prompts present
their data as text so the bank is self-contained without images. The seed is
applied idempotently by migration 0012 and by ``seed.seed_ielts``.

``key`` is a stable identifier used to derive deterministic UUIDs; never
change an existing key (it would create a duplicate question).
"""

SEED_TAGS: list[dict[str, str]] = [
    {"name": "Education", "slug": "education"},
    {"name": "Environment", "slug": "environment"},
    {"name": "Technology", "slug": "technology"},
    {"name": "Health", "slug": "health"},
    {"name": "Work", "slug": "work"},
    {"name": "Culture", "slug": "culture"},
    {"name": "Urbanisation", "slug": "urbanisation"},
    {"name": "Globalisation", "slug": "globalisation"},
    {"name": "Media", "slug": "media"},
    {"name": "Government", "slug": "government"},
    {"name": "Transport", "slug": "transport"},
    {"name": "Crime", "slug": "crime"},
    {"name": "Family", "slug": "family"},
    {"name": "Sports", "slug": "sports"},
    {"name": "Tourism", "slug": "tourism"},
    {"name": "Science", "slug": "science"},
    {"name": "Language", "slug": "language"},
    {"name": "Consumerism", "slug": "consumerism"},
]

_T1_INSTRUCTIONS = (
    "Summarise the information by selecting and reporting the main features, "
    "and make comparisons where relevant. Write at least 150 words."
)
_T1_INSTRUCTIONS_ZH = "请总结信息，选择并报告主要特征，并在相关处进行比较。不少于150词。"
_T2_INSTRUCTIONS = (
    "Give reasons for your answer and include any relevant examples from your own "
    "knowledge or experience. Write at least 250 words."
)
_T2_INSTRUCTIONS_ZH = "请给出理由，并结合自身知识或经验举出相关例子。不少于250词。"

SEED_QUESTIONS: list[dict] = [
    # ------------------------------------------------------------------
    # Task 1 Academic — line graphs
    # ------------------------------------------------------------------
    {
        "key": "t1-line-museums",
        "task_type": "task1",
        "question_type": "line_graph",
        "difficulty": "medium",
        "tags": ["culture", "tourism"],
        "prompt_text": (
            "The line graph below shows the number of visitors to three London museums "
            "between 2010 and 2020.\n\n"
            "Data (visitors, millions):\n"
            "- British Museum: 2010: 5.8; 2015: 6.8; 2020: 6.0\n"
            "- Natural History Museum: 2010: 4.6; 2015: 5.3; 2020: 5.0\n"
            "- Science Museum: 2010: 2.9; 2015: 3.4; 2020: 3.1\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的折线图显示了2010年至2020年伦敦三家博物馆的游客数量（单位：百万）。"
            "大英博物馆：2010年5.8，2015年6.8，2020年6.0；自然历史博物馆：4.6、5.3、5.0；"
            "科学博物馆：2.9、3.4、3.1。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t1-line-renewables",
        "task_type": "task1",
        "question_type": "line_graph",
        "difficulty": "medium",
        "tags": ["environment", "science"],
        "prompt_text": (
            "The line graph below shows the share of electricity generated from renewable "
            "sources in three countries from 2000 to 2020.\n\n"
            "Data (share of electricity, %):\n"
            "- Country A: 2000: 8; 2005: 11; 2010: 17; 2015: 26; 2020: 38\n"
            "- Country B: 2000: 22; 2005: 24; 2010: 27; 2015: 30; 2020: 33\n"
            "- Country C: 2000: 45; 2005: 46; 2010: 48; 2015: 51; 2020: 54\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的折线图显示了2000年至2020年三个国家可再生能源发电占比（%）。"
            "A国：8、11、17、26、38；B国：22、24、27、30、33；C国：45、46、48、51、54"
            "（每五年一个数据点）。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t1-line-working-hours",
        "task_type": "task1",
        "question_type": "line_graph",
        "difficulty": "hard",
        "tags": ["work"],
        "prompt_text": (
            "The line graph below shows average weekly working hours per employee in four "
            "countries between 1990 and 2020.\n\n"
            "Data (hours per week):\n"
            "- Country A: 1990: 42; 2000: 40; 2010: 38; 2020: 36\n"
            "- Country B: 1990: 46; 2000: 44; 2010: 43; 2020: 41\n"
            "- Country C: 1990: 38; 2000: 37; 2010: 37; 2020: 35\n"
            "- Country D: 1990: 40; 2000: 41; 2010: 39; 2020: 37\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的折线图显示了1990年至2020年四个国家雇员的平均每周工作时长（小时）。"
            "A国：42、40、38、36；B国：46、44、43、41；C国：38、37、37、35；"
            "D国：40、41、39、37（每十年一个数据点）。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    # ------------------------------------------------------------------
    # Task 1 Academic — bar charts
    # ------------------------------------------------------------------
    {
        "key": "t1-bar-chores",
        "task_type": "task1",
        "question_type": "bar_chart",
        "difficulty": "easy",
        "tags": ["family", "work"],
        "prompt_text": (
            "The bar chart below shows the average number of hours per week that men and "
            "women spend on household chores in five countries.\n\n"
            "Data (hours per week, women / men):\n"
            "- Country A: 24 / 10\n"
            "- Country B: 20 / 12\n"
            "- Country C: 18 / 14\n"
            "- Country D: 15 / 11\n"
            "- Country E: 12 / 9\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的柱状图显示了五个国家男性和女性每周做家务的平均时长（小时，女/男）。"
            "A国：24/10；B国：20/12；C国：18/14；D国：15/11；E国：12/9。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t1-bar-enrolments",
        "task_type": "task1",
        "question_type": "bar_chart",
        "difficulty": "medium",
        "tags": ["education"],
        "prompt_text": (
            "The bar chart below shows the number of students enrolled in five subjects at "
            "a university in 2015 and 2020.\n\n"
            "Data (students, 2015 / 2020):\n"
            "- Business: 1,200 / 1,450\n"
            "- Computer Science: 800 / 1,600\n"
            "- Engineering: 950 / 900\n"
            "- History: 400 / 280\n"
            "- Biology: 650 / 720\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的柱状图显示了某大学2015年和2020年五个专业的在读学生人数（2015/2020）。"
            "商科：1200/1450；计算机科学：800/1600；工程：950/900；历史：400/280；"
            "生物：650/720。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t1-bar-emissions",
        "task_type": "task1",
        "question_type": "bar_chart",
        "difficulty": "medium",
        "tags": ["environment", "globalisation"],
        "prompt_text": (
            "The bar chart below shows carbon dioxide emissions per person in six countries "
            "in 2019.\n\n"
            "Data (tonnes of CO2 per person):\n"
            "- Country A: 15.2\n"
            "- Country B: 12.8\n"
            "- Country C: 7.4\n"
            "- Country D: 6.1\n"
            "- Country E: 2.3\n"
            "- Country F: 1.1\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的柱状图显示了2019年六个国家的人均二氧化碳排放量（吨/人）。"
            "A国：15.2；B国：12.8；C国：7.4；D国：6.1；E国：2.3；F国：1.1。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    # ------------------------------------------------------------------
    # Task 1 Academic — pie charts
    # ------------------------------------------------------------------
    {
        "key": "t1-pie-spending",
        "task_type": "task1",
        "question_type": "pie_chart",
        "difficulty": "easy",
        "tags": ["consumerism", "family"],
        "prompt_text": (
            "The pie charts below show how an average household in two countries divided "
            "its spending in 2020.\n\n"
            "Data (share of total spending, %):\n"
            "- Country A: housing 32; food 24; transport 16; leisure 12; other 16\n"
            "- Country B: housing 26; food 34; transport 12; leisure 10; other 18\n\n"
            + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的饼图显示了2020年两个国家普通家庭的支出构成（占总支出百分比）。"
            "A国：住房32、食品24、交通16、休闲12、其他16；"
            "B国：住房26、食品34、交通12、休闲10、其他18。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t1-pie-energy-mix",
        "task_type": "task1",
        "question_type": "pie_chart",
        "difficulty": "medium",
        "tags": ["environment", "science"],
        "prompt_text": (
            "The pie charts below show the energy mix of a country in 2000 and 2020.\n\n"
            "Data (share of total energy, %, 2000 / 2020):\n"
            "- Coal: 40 / 18\n"
            "- Oil: 30 / 26\n"
            "- Gas: 18 / 24\n"
            "- Nuclear: 8 / 12\n"
            "- Renewables: 4 / 20\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的饼图显示了某国2000年和2020年的能源结构（占总能源百分比，2000/2020）。"
            "煤炭：40/18；石油：30/26；天然气：18/24；核能：8/12；可再生能源：4/20。"
            + _T1_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t1-pie-commute",
        "task_type": "task1",
        "question_type": "pie_chart",
        "difficulty": "easy",
        "tags": ["transport", "education"],
        "prompt_text": (
            "The pie chart below shows how students at a university travel to campus.\n\n"
            "Data (share of students, %):\n"
            "- Bus: 34\n"
            "- Bicycle: 22\n"
            "- On foot: 18\n"
            "- Car: 14\n"
            "- Train: 9\n"
            "- Other: 3\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的饼图显示了某大学学生到校的出行方式（占学生比例%）。"
            "公交34、自行车22、步行18、私家车14、火车9、其他3。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    # ------------------------------------------------------------------
    # Task 1 Academic — tables
    # ------------------------------------------------------------------
    {
        "key": "t1-table-attractions",
        "task_type": "task1",
        "question_type": "table",
        "difficulty": "medium",
        "tags": ["tourism"],
        "prompt_text": (
            "The table below shows visitor numbers and average spending at four tourist "
            "attractions in one city in 2022.\n\n"
            "Data (visitors, thousands / average spending per visitor, $):\n"
            "- City museum: 850 / 12\n"
            "- Old town walking tours: 620 / 35\n"
            "- Theme park: 1,100 / 58\n"
            "- Botanical garden: 340 / 8\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的表格显示了2022年某城市四个旅游景点的游客数量和人均消费"
            "（游客量：千人次 / 人均消费：美元）。"
            "城市博物馆：850/12；老城徒步游：620/35；主题公园：1100/58；植物园：340/8。"
            + _T1_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t1-table-internet",
        "task_type": "task1",
        "question_type": "table",
        "difficulty": "medium",
        "tags": ["technology", "globalisation"],
        "prompt_text": (
            "The table below shows the percentage of people with internet access in five "
            "regions in 2010, 2015 and 2020.\n\n"
            "Data (% of population, 2010 / 2015 / 2020):\n"
            "- Region A: 78 / 86 / 93\n"
            "- Region B: 62 / 74 / 85\n"
            "- Region C: 35 / 52 / 71\n"
            "- Region D: 21 / 38 / 60\n"
            "- Region E: 12 / 25 / 44\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的表格显示了2010、2015和2020年五个地区可接入互联网的人口比例"
            "（%，2010/2015/2020）。A地区：78/86/93；B地区：62/74/85；C地区：35/52/71；"
            "D地区：21/38/60；E地区：12/25/44。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t1-table-salaries",
        "task_type": "task1",
        "question_type": "table",
        "difficulty": "hard",
        "tags": ["work"],
        "prompt_text": (
            "The table below shows average annual salary and reported job satisfaction in "
            "five professions in one country.\n\n"
            "Data (salary, $ / satisfaction, % reporting 'satisfied'):\n"
            "- Software developer: 72,000 / 74\n"
            "- Nurse: 48,000 / 68\n"
            "- Secondary school teacher: 44,000 / 62\n"
            "- Retail manager: 38,000 / 51\n"
            "- Delivery driver: 31,000 / 46\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的表格显示了某国五种职业的平均年薪和工作满意度"
            "（年薪：美元 / 满意度：表示'满意'的比例%）。"
            "软件开发：72000/74；护士：48000/68；中学教师：44000/62；"
            "零售经理：38000/51；配送司机：31000/46。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    # ------------------------------------------------------------------
    # Task 1 Academic — processes
    # ------------------------------------------------------------------
    {
        "key": "t1-process-recycled-paper",
        "task_type": "task1",
        "question_type": "process",
        "difficulty": "medium",
        "tags": ["environment", "science"],
        "prompt_text": (
            "The diagram below shows how recycled paper is produced.\n\n"
            "Stages:\n"
            "1. Used paper is collected from homes and offices.\n"
            "2. The paper is sorted and cleaned to remove plastic and ink.\n"
            "3. It is mixed with water and broken down into pulp.\n"
            "4. The pulp is screened and washed again.\n"
            "5. The clean pulp is spread flat, pressed and dried into new sheets.\n"
            "6. The sheets are rolled, cut and packaged for sale.\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的流程图展示了再生纸的生产过程：1. 从家庭和办公室收集废纸；"
            "2. 分拣并清除塑料和油墨；3. 加水碎解成纸浆；4. 再次筛选和清洗；"
            "5. 铺平、压榨、烘干成新纸张；6. 卷筒、裁切、包装出售。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t1-process-coffee",
        "task_type": "task1",
        "question_type": "process",
        "difficulty": "medium",
        "tags": ["consumerism", "science"],
        "prompt_text": (
            "The diagram below shows how coffee is produced, from farm to cup.\n\n"
            "Stages:\n"
            "1. Coffee cherries are picked by hand when ripe.\n"
            "2. The beans are removed from the fruit and dried in the sun.\n"
            "3. The dried beans are roasted at high temperature.\n"
            "4. The roasted beans are ground into powder.\n"
            "5. The powder is brewed with hot water.\n"
            "6. The coffee is served.\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的流程图展示了咖啡从农场到杯中的生产过程：1. 人工采摘成熟的咖啡果；"
            "2. 取出咖啡豆并晒干；3. 高温烘焙；4. 研磨成粉；5. 用热水冲泡；6. 出品饮用。"
            + _T1_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t1-process-online-order",
        "task_type": "task1",
        "question_type": "process",
        "difficulty": "easy",
        "tags": ["technology", "consumerism"],
        "prompt_text": (
            "The diagram below shows how an online order is fulfilled.\n\n"
            "Stages:\n"
            "1. A customer places an order on the website.\n"
            "2. Payment is checked and confirmed.\n"
            "3. The warehouse system locates the items.\n"
            "4. Items are picked, packed and labelled.\n"
            "5. A courier collects the parcel and delivers it.\n"
            "6. The customer confirms receipt online.\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的流程图展示了线上订单的履约过程：1. 顾客在网站下单；2. 核验并确认付款；"
            "3. 仓储系统定位商品；4. 拣货、打包、贴标；5. 快递员揽收并派送；"
            "6. 顾客在线确认收货。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    # ------------------------------------------------------------------
    # Task 1 Academic — maps
    # ------------------------------------------------------------------
    {
        "key": "t1-map-town-centre",
        "task_type": "task1",
        "question_type": "map",
        "difficulty": "hard",
        "tags": ["urbanisation", "transport"],
        "prompt_text": (
            "The maps below show a town centre in 2000 and today.\n\n"
            "2000: a main road runs east-west through the centre. North of the road are a "
            "market square and a small library; south of the road are rows of shops and a "
            "car park. A river lies at the eastern edge, with no crossing.\n\n"
            "Today: the main road is pedestrianised. The market square remains, but the "
            "library has been replaced by a shopping mall. The southern shops are now "
            "cafes and restaurants, and the car park has become a public garden. A new "
            "footbridge crosses the river to a housing area on the east bank.\n\n"
            + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的两幅地图展示了某镇中心2000年与今天的布局。2000年：一条主干道东西向穿过中心，"
            "路北是集市广场和一座小图书馆，路南是成排商店和停车场，东侧边缘有一条河，无过河通道。"
            "今天：主干道改为步行街；集市广场保留，图书馆被购物中心取代；南侧商店改为咖啡馆和餐厅，"
            "停车场变成公共花园；新建人行桥通往河东岸的住宅区。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t1-map-campus",
        "task_type": "task1",
        "question_type": "map",
        "difficulty": "medium",
        "tags": ["education", "urbanisation"],
        "prompt_text": (
            "The maps below show a university campus in 2010 and in 2025.\n\n"
            "2010: the entrance is on the south side. A central lawn is surrounded by "
            "three teaching buildings, a library to the west and a small canteen to the "
            "east. Student dormitories are in the north-west corner; there is no sports "
            "facility.\n\n"
            "2025: the entrance has moved to the east. Two teaching buildings remain and "
            "the third has become a research centre. The library has been extended. The "
            "canteen has been replaced by a student centre with shops. A sports hall and "
            "an outdoor track now occupy the north-east corner, and the dormitories have "
            "been rebuilt as taller blocks in the same north-west area.\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的两幅地图展示了某大学校园2010年与2025年的布局。2010年：入口在南侧，中央草坪周围"
            "有三栋教学楼，西侧是图书馆，东侧是小食堂，西北角是学生宿舍，无体育设施。"
            "2025年：入口移至东侧；两栋教学楼保留，第三栋改为研究中心；图书馆扩建；"
            "食堂改为带商铺的学生中心；东北角新建体育馆和室外跑道；西北角宿舍原址重建为更高的楼栋。"
            + _T1_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t1-map-coastal-village",
        "task_type": "task1",
        "question_type": "map",
        "difficulty": "hard",
        "tags": ["transport", "tourism", "urbanisation"],
        "prompt_text": (
            "The maps below show a coastal village before and after a new harbour was built.\n\n"
            "Before: a single road leads into the village from the north. Houses cluster "
            "around a small church. The shore to the south has a fishing beach and a few "
            "boat sheds. Farmland lies to the west.\n\n"
            "After: the harbour occupies the former fishing beach, with a pier and a "
            "marina. The boat sheds have been converted into restaurants. A new road "
            "connects the harbour to a hotel and a car park built on part of the farmland. "
            "The church and the original houses remain unchanged.\n\n" + _T1_INSTRUCTIONS
        ),
        "prompt_translation": (
            "下面的两幅地图展示了某海滨村庄修建新港口前后的布局。之前：一条路从北面进村，"
            "房屋围绕一座小教堂，南面海岸是渔滩和几间船棚，西面是农田。"
            "之后：港口占据原渔滩，建有码头和游艇泊位；船棚改为餐厅；新路连接港口与建在部分农田上的"
            "酒店和停车场；教堂和原有房屋保持不变。" + _T1_INSTRUCTIONS_ZH
        ),
    },
    # ------------------------------------------------------------------
    # Task 1 General Training — letters
    # ------------------------------------------------------------------
    {
        "key": "t1-letter-lost-luggage",
        "task_type": "task1",
        "question_type": "letter_formal",
        "difficulty": "easy",
        "tags": ["tourism", "transport"],
        "prompt_text": (
            "You recently flew with an airline and your suitcase did not arrive. You have "
            "already reported the problem at the airport, but nobody has contacted you.\n\n"
            "Write a letter to the airline. In your letter:\n"
            "- describe your flight and the suitcase\n"
            "- explain what you have done so far\n"
            "- say what you want the airline to do\n\n"
            "Write at least 150 words. You do NOT need to write any addresses. Begin your "
            "letter 'Dear Sir or Madam,'."
        ),
        "prompt_translation": (
            "你最近乘坐某航空公司的航班，行李箱没有送达。你已在机场报告问题，但一直无人联系你。"
            "请给航空公司写一封信：描述你的航班和行李箱；说明你目前已采取的行动；"
            "提出你希望航空公司如何处理。不少于150词，无需写地址，以'Dear Sir or Madam,'开头。"
        ),
    },
    {
        "key": "t1-letter-road-repairs",
        "task_type": "task1",
        "question_type": "letter_formal",
        "difficulty": "medium",
        "tags": ["transport", "government", "urbanisation"],
        "prompt_text": (
            "The road outside your home has been in poor condition for several months, "
            "and it is becoming dangerous for pedestrians and cyclists.\n\n"
            "Write a letter to the local council. In your letter:\n"
            "- describe the condition of the road\n"
            "- explain the problems it causes\n"
            "- say what action you would like the council to take\n\n"
            "Write at least 150 words. You do NOT need to write any addresses. Begin your "
            "letter 'Dear Sir or Madam,'."
        ),
        "prompt_translation": (
            "你家外面的路况数月来一直很差，对行人和骑行者越来越危险。请给地方议会写一封信："
            "描述道路状况；说明它造成的问题；提出你希望议会采取的措施。"
            "不少于150词，无需写地址，以'Dear Sir or Madam,'开头。"
        ),
    },
    {
        "key": "t1-letter-defective-product",
        "task_type": "task1",
        "question_type": "letter_formal",
        "difficulty": "medium",
        "tags": ["consumerism"],
        "prompt_text": (
            "You bought an electrical appliance from an online store, but it stopped "
            "working after two weeks. You have tried to contact the store by email "
            "without success.\n\n"
            "Write a letter to the store manager. In your letter:\n"
            "- give details of the purchase and the fault\n"
            "- explain how you have tried to resolve the problem\n"
            "- say what you expect the store to do\n\n"
            "Write at least 150 words. You do NOT need to write any addresses. Begin your "
            "letter 'Dear Sir or Madam,'."
        ),
        "prompt_translation": (
            "你在一家网店购买了一件电器，两周后就无法使用。你尝试通过邮件联系商店但未获回应。"
            "请给商店经理写一封信：说明购买详情和故障；解释你已尝试的解决方式；"
            "提出你期望商店如何处理。不少于150词，无需写地址，以'Dear Sir or Madam,'开头。"
        ),
    },
    {
        "key": "t1-letter-landlord-heating",
        "task_type": "task1",
        "question_type": "letter_semi_formal",
        "difficulty": "easy",
        "tags": ["urbanisation", "family"],
        "prompt_text": (
            "The heating system in the flat you rent has broken, and the weather is "
            "getting cold. Your landlord lives in another city.\n\n"
            "Write a letter to your landlord. In your letter:\n"
            "- describe the problem with the heating\n"
            "- explain how it is affecting you\n"
            "- suggest how and when it could be repaired\n\n"
            "Write at least 150 words. You do NOT need to write any addresses. Begin your "
            "letter 'Dear Mr Taylor,'."
        ),
        "prompt_translation": (
            "你租住的公寓供暖系统坏了，天气越来越冷，房东住在另一座城市。请给房东写一封信："
            "描述供暖问题；说明它对你的影响；建议维修的方式和时间。"
            "不少于150词，无需写地址，以'Dear Mr Taylor,'开头。"
        ),
    },
    {
        "key": "t1-letter-colleague-talk",
        "task_type": "task1",
        "question_type": "letter_semi_formal",
        "difficulty": "medium",
        "tags": ["work"],
        "prompt_text": (
            "You are organising a training day at your company and would like a former "
            "colleague, who now works elsewhere, to give a talk.\n\n"
            "Write a letter to your former colleague. In your letter:\n"
            "- explain what the training day is about\n"
            "- say why you would like them to speak\n"
            "- give practical details and ask about their availability\n\n"
            "Write at least 150 words. You do NOT need to write any addresses. Begin your "
            "letter 'Dear Ms Chen,'."
        ),
        "prompt_translation": (
            "你正在组织公司培训日，想邀请一位已离职的前同事来做分享。请给这位前同事写一封信："
            "说明培训日的主题；解释为什么想邀请对方演讲；提供具体安排并询问对方是否有空。"
            "不少于150词，无需写地址，以'Dear Ms Chen,'开头。"
        ),
    },
    {
        "key": "t1-letter-neighbour-noise",
        "task_type": "task1",
        "question_type": "letter_semi_formal",
        "difficulty": "medium",
        "tags": ["family", "urbanisation"],
        "prompt_text": (
            "Your neighbour is having building work done at home, and the noise is "
            "disturbing you while you work from home.\n\n"
            "Write a letter to your neighbour. In your letter:\n"
            "- describe the problem the noise causes\n"
            "- explain your situation\n"
            "- suggest a compromise\n\n"
            "Write at least 150 words. You do NOT need to write any addresses. Begin your "
            "letter 'Dear Mr and Mrs Patel,'."
        ),
        "prompt_translation": (
            "你的邻居正在家中施工，噪音影响了在家办公的你。请给邻居写一封信："
            "描述噪音造成的问题；解释你的情况；提出一个折中方案。"
            "不少于150词，无需写地址，以'Dear Mr and Mrs Patel,'开头。"
        ),
    },
    {
        "key": "t1-letter-friend-visit",
        "task_type": "task1",
        "question_type": "letter_informal",
        "difficulty": "easy",
        "tags": ["tourism", "family"],
        "prompt_text": (
            "An English-speaking friend is planning to visit your city for the first time "
            "and has asked for your advice.\n\n"
            "Write a letter to your friend. In your letter:\n"
            "- suggest the best time of year to visit\n"
            "- recommend places to see and things to do\n"
            "- offer to help with accommodation\n\n"
            "Write at least 150 words. You do NOT need to write any addresses. Begin your "
            "letter 'Dear Alex,'."
        ),
        "prompt_translation": (
            "一位说英语的朋友计划第一次来你所在的城市，向你征求建议。请给朋友写一封信："
            "建议最佳来访季节；推荐值得游览的地点和活动；主动提出帮忙安排住宿。"
            "不少于150词，无需写地址，以'Dear Alex,'开头。"
        ),
    },
    {
        "key": "t1-letter-friend-apology",
        "task_type": "task1",
        "question_type": "letter_informal",
        "difficulty": "easy",
        "tags": ["family"],
        "prompt_text": (
            "You missed your friend's birthday party because of an unexpected problem at "
            "work.\n\n"
            "Write a letter to your friend. In your letter:\n"
            "- apologise for missing the party\n"
            "- explain what happened\n"
            "- suggest a way to make it up to them\n\n"
            "Write at least 150 words. You do NOT need to write any addresses. Begin your "
            "letter 'Dear Sam,'."
        ),
        "prompt_translation": (
            "你因为工作中突发的问题错过了朋友的生日聚会。请给朋友写一封信："
            "为缺席道歉；解释发生了什么；提出弥补的方式。"
            "不少于150词，无需写地址，以'Dear Sam,'开头。"
        ),
    },
    {
        "key": "t1-letter-friend-job-advice",
        "task_type": "task1",
        "question_type": "letter_informal",
        "difficulty": "medium",
        "tags": ["work", "family"],
        "prompt_text": (
            "You have received two job offers and cannot decide which one to accept. You "
            "want to ask a friend who knows you well for advice.\n\n"
            "Write a letter to your friend. In your letter:\n"
            "- describe the two offers\n"
            "- explain what makes the decision difficult\n"
            "- ask for your friend's opinion\n\n"
            "Write at least 150 words. You do NOT need to write any addresses. Begin your "
            "letter 'Dear Jordan,'."
        ),
        "prompt_translation": (
            "你收到两份工作邀请，难以决定接受哪一份，想请一位了解你的朋友给出建议。"
            "请给朋友写一封信：描述两份邀请；解释决定的难点；征求朋友的意见。"
            "不少于150词，无需写地址，以'Dear Jordan,'开头。"
        ),
    },
    # ------------------------------------------------------------------
    # Task 2 — opinion (agree / disagree)
    # ------------------------------------------------------------------
    {
        "key": "t2-opinion-free-university",
        "task_type": "task2",
        "question_type": "opinion",
        "difficulty": "medium",
        "tags": ["education", "government"],
        "prompt_text": (
            "Some people think that university education should be free for everyone. "
            "To what extent do you agree or disagree?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为大学教育应该对所有人免费。你在多大程度上同意或不同意？" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-opinion-social-media-harm",
        "task_type": "task2",
        "question_type": "opinion",
        "difficulty": "medium",
        "tags": ["media", "technology"],
        "prompt_text": (
            "Some people believe that social media has done more harm than good to "
            "society. To what extent do you agree or disagree?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为社交媒体对社会弊大于利。你在多大程度上同意或不同意？" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-opinion-public-services-arts",
        "task_type": "task2",
        "question_type": "opinion",
        "difficulty": "hard",
        "tags": ["government", "culture"],
        "prompt_text": (
            "Some people think that governments should spend money on public services "
            "rather than on the arts. To what extent do you agree or disagree?\n\n"
            + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为政府应该把钱花在公共服务上，而不是艺术上。你在多大程度上同意或不同意？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-opinion-early-language",
        "task_type": "task2",
        "question_type": "opinion",
        "difficulty": "easy",
        "tags": ["education", "language"],
        "prompt_text": (
            "Some people believe that children should start learning a foreign language "
            "as early as possible. To what extent do you agree or disagree?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为儿童应该尽早开始学习外语。你在多大程度上同意或不同意？" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-opinion-working-from-home",
        "task_type": "task2",
        "question_type": "opinion",
        "difficulty": "easy",
        "tags": ["work", "technology"],
        "prompt_text": (
            "Some people think that working from home is better for employees than "
            "working in an office. To what extent do you agree or disagree?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为居家办公比在办公室工作对员工更有利。你在多大程度上同意或不同意？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-opinion-individuals-environment",
        "task_type": "task2",
        "question_type": "opinion",
        "difficulty": "hard",
        "tags": ["environment", "government"],
        "prompt_text": (
            "Some people believe that individual actions cannot make a difference to the "
            "environment, and that only governments and large companies can solve "
            "environmental problems. To what extent do you agree or disagree?\n\n"
            + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为个人行为无法改变环境，只有政府和大公司才能解决环境问题。"
            "你在多大程度上同意或不同意？" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-opinion-competitive-sports",
        "task_type": "task2",
        "question_type": "opinion",
        "difficulty": "medium",
        "tags": ["sports", "education", "health"],
        "prompt_text": (
            "Some people think that competitive sports should be a compulsory part of "
            "school life. To what extent do you agree or disagree?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为竞技体育应该成为学校生活的必修部分。你在多大程度上同意或不同意？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    # ------------------------------------------------------------------
    # Task 2 — discussion (both views)
    # ------------------------------------------------------------------
    {
        "key": "t2-discussion-online-classrooms",
        "task_type": "task2",
        "question_type": "discussion",
        "difficulty": "medium",
        "tags": ["education", "technology"],
        "prompt_text": (
            "Some people think that online learning will eventually replace traditional "
            "classrooms. Others believe that face-to-face teaching will always be "
            "necessary. Discuss both views and give your own opinion.\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为在线学习最终会取代传统课堂；也有人认为面对面教学永远不可或缺。"
            "讨论双方观点并给出你自己的看法。" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-discussion-growth-environment",
        "task_type": "task2",
        "question_type": "discussion",
        "difficulty": "hard",
        "tags": ["environment", "globalisation"],
        "prompt_text": (
            "Some people believe that economic growth is the most important goal for a "
            "country. Others think that protecting the environment should come first. "
            "Discuss both views and give your own opinion.\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为经济增长是一个国家最重要的目标；也有人认为环境保护应放在首位。"
            "讨论双方观点并给出你自己的看法。" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-discussion-free-museums",
        "task_type": "task2",
        "question_type": "discussion",
        "difficulty": "medium",
        "tags": ["culture", "government", "tourism"],
        "prompt_text": (
            "Some people think that museums should be free for everyone. Others believe "
            "that charging admission is necessary to maintain them. Discuss both views "
            "and give your own opinion.\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为博物馆应该对所有人免费开放；也有人认为收取门票是维持运营的必要手段。"
            "讨论双方观点并给出你自己的看法。" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-discussion-parents-crime",
        "task_type": "task2",
        "question_type": "discussion",
        "difficulty": "hard",
        "tags": ["crime", "family"],
        "prompt_text": (
            "Some people think that parents should be held responsible for their "
            "children's criminal behaviour. Others believe that society shares the "
            "responsibility. Discuss both views and give your own opinion.\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为父母应为孩子的犯罪行为承担责任；也有人认为社会同样负有责任。"
            "讨论双方观点并给出你自己的看法。" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-discussion-press-freedom",
        "task_type": "task2",
        "question_type": "discussion",
        "difficulty": "hard",
        "tags": ["media", "government"],
        "prompt_text": (
            "Some people believe that news media should be free to report on any topic. "
            "Others think that some restrictions are necessary. Discuss both views and "
            "give your own opinion.\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为新闻媒体应有权报道任何话题；也有人认为必要的限制不可少。"
            "讨论双方观点并给出你自己的看法。" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-discussion-cars-cities",
        "task_type": "task2",
        "question_type": "discussion",
        "difficulty": "medium",
        "tags": ["transport", "urbanisation", "environment"],
        "prompt_text": (
            "Some people think that cities should be designed around the car. Others "
            "believe that public transport and cycling should be given priority. Discuss "
            "both views and give your own opinion.\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为城市应围绕汽车来规划；也有人认为应优先发展公共交通和骑行。"
            "讨论双方观点并给出你自己的看法。" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-discussion-tourism-impact",
        "task_type": "task2",
        "question_type": "discussion",
        "difficulty": "medium",
        "tags": ["tourism", "globalisation", "culture"],
        "prompt_text": (
            "Some people believe that international tourism benefits local communities. "
            "Others think that it damages local culture and the environment. Discuss "
            "both views and give your own opinion.\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人认为国际旅游有利于当地社区；也有人认为它破坏当地文化和环境。"
            "讨论双方观点并给出你自己的看法。" + _T2_INSTRUCTIONS_ZH
        ),
    },
    # ------------------------------------------------------------------
    # Task 2 — advantages / disadvantages
    # ------------------------------------------------------------------
    {
        "key": "t2-adv-online-shopping",
        "task_type": "task2",
        "question_type": "advantages_disadvantages",
        "difficulty": "easy",
        "tags": ["consumerism", "technology"],
        "prompt_text": (
            "More and more people are shopping online instead of in physical stores. "
            "Do the advantages of this trend outweigh the disadvantages?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "越来越多的人选择网购而不是去实体店购物。这一趋势的利是否大于弊？" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-adv-rural-to-city",
        "task_type": "task2",
        "question_type": "advantages_disadvantages",
        "difficulty": "medium",
        "tags": ["urbanisation", "work"],
        "prompt_text": (
            "In many countries, young people are moving from rural areas to large "
            "cities. Do the advantages of this trend outweigh the disadvantages?\n\n"
            + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "在许多国家，年轻人正从农村迁往大城市。这一趋势的利是否大于弊？" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-adv-digital-textbooks",
        "task_type": "task2",
        "question_type": "advantages_disadvantages",
        "difficulty": "medium",
        "tags": ["education", "technology"],
        "prompt_text": (
            "Some schools are replacing printed textbooks with digital devices. Do the "
            "advantages of this development outweigh the disadvantages?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "一些学校正在用电子设备取代纸质教材。这一发展的利是否大于弊？" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-adv-work-anywhere",
        "task_type": "task2",
        "question_type": "advantages_disadvantages",
        "difficulty": "hard",
        "tags": ["work", "globalisation", "technology"],
        "prompt_text": (
            "An increasing number of companies allow employees to work from anywhere in "
            "the world. Do the advantages of this trend outweigh the disadvantages?\n\n"
            + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "越来越多的公司允许员工在世界各地远程工作。这一趋势的利是否大于弊？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-adv-streaming",
        "task_type": "task2",
        "question_type": "advantages_disadvantages",
        "difficulty": "easy",
        "tags": ["media", "technology"],
        "prompt_text": (
            "Many people now use streaming services instead of watching traditional "
            "television. Do the advantages of this change outweigh the disadvantages?\n\n"
            + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "如今许多人使用流媒体服务而不是传统电视。这一变化的利是否大于弊？" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-adv-later-parenthood",
        "task_type": "task2",
        "question_type": "advantages_disadvantages",
        "difficulty": "hard",
        "tags": ["family", "health"],
        "prompt_text": (
            "In some countries, people are having children later in life than in the "
            "past. Do the advantages of this trend outweigh the disadvantages?\n\n"
            + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "在一些国家，人们生育孩子的年龄比过去更晚。这一趋势的利是否大于弊？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    # ------------------------------------------------------------------
    # Task 2 — problem / solution
    # ------------------------------------------------------------------
    {
        "key": "t2-prob-traffic",
        "task_type": "task2",
        "question_type": "problem_solution",
        "difficulty": "medium",
        "tags": ["transport", "urbanisation", "government"],
        "prompt_text": (
            "In many cities, traffic congestion is getting worse. What problems does "
            "this cause, and what measures can governments take to reduce it?\n\n"
            + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "许多城市的交通拥堵日益严重。这会造成哪些问题？政府可以采取哪些措施缓解？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-prob-smartphones",
        "task_type": "task2",
        "question_type": "problem_solution",
        "difficulty": "easy",
        "tags": ["technology", "health", "family", "education"],
        "prompt_text": (
            "Many young people today spend too much time on their smartphones. What "
            "problems does this cause, and what can parents and schools do about it?\n\n"
            + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "如今许多年轻人在智能手机上花费过多时间。这会造成哪些问题？家长和学校可以怎么做？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-prob-ocean-plastic",
        "task_type": "task2",
        "question_type": "problem_solution",
        "difficulty": "medium",
        "tags": ["environment", "globalisation"],
        "prompt_text": (
            "The amount of plastic waste in the oceans is increasing. What problems does "
            "this cause, and what solutions can you suggest?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "海洋中的塑料垃圾越来越多。这会造成哪些问题？你能提出哪些解决方案？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-prob-ageing-population",
        "task_type": "task2",
        "question_type": "problem_solution",
        "difficulty": "hard",
        "tags": ["health", "government", "family"],
        "prompt_text": (
            "In many countries, the population is ageing. What problems does this cause "
            "for society, and how can governments prepare for it?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "许多国家的人口正在老龄化。这会给社会带来哪些问题？政府应如何应对？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-prob-graduate-jobs",
        "task_type": "task2",
        "question_type": "problem_solution",
        "difficulty": "medium",
        "tags": ["education", "work", "government"],
        "prompt_text": (
            "Many graduates struggle to find jobs related to their degree. What are the "
            "causes of this problem, and what can universities and governments do to "
            "help?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "许多毕业生难以找到与专业相关的工作。这一问题的成因是什么？大学和政府可以如何提供帮助？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-prob-obesity",
        "task_type": "task2",
        "question_type": "problem_solution",
        "difficulty": "easy",
        "tags": ["health", "consumerism", "sports"],
        "prompt_text": (
            "Obesity rates are rising in many countries, especially among children. What "
            "are the causes of this problem, and what measures can be taken to address "
            "it?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "许多国家的肥胖率不断上升，儿童尤为明显。这一问题的成因是什么？可以采取哪些措施应对？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    # ------------------------------------------------------------------
    # Task 2 — two-part questions
    # ------------------------------------------------------------------
    {
        "key": "t2-two-neighbours",
        "task_type": "task2",
        "question_type": "two_part",
        "difficulty": "medium",
        "tags": ["urbanisation", "family"],
        "prompt_text": (
            "Many people today do not know their neighbours. Why is this happening? "
            "What can be done to build stronger local communities?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "如今许多人不认识自己的邻居。为什么会出现这种情况？可以做些什么来建设更紧密的社区？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-two-stay-or-move",
        "task_type": "task2",
        "question_type": "two_part",
        "difficulty": "medium",
        "tags": ["urbanisation", "family", "work"],
        "prompt_text": (
            "Some people choose to live in the same city all their lives, while others "
            "move several times. Why do people make these different choices? Which do "
            "you think is better?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "有人选择一辈子住在同一座城市，也有人多次搬迁。人们为什么会做出不同的选择？"
            "你认为哪种更好？" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-two-traditional-crafts",
        "task_type": "task2",
        "question_type": "two_part",
        "difficulty": "hard",
        "tags": ["culture", "globalisation"],
        "prompt_text": (
            "In many countries, traditional skills and crafts are dying out. Why is this "
            "happening? How can these skills be preserved?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "在许多国家，传统技艺和手工艺正在消亡。为什么会出现这种情况？如何保护这些技艺？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-two-disposable-products",
        "task_type": "task2",
        "question_type": "two_part",
        "difficulty": "medium",
        "tags": ["consumerism", "environment"],
        "prompt_text": (
            "More people are choosing to buy cheap, disposable products rather than "
            "durable ones. Why is this happening? Is this a positive or a negative "
            "development?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "越来越多的人购买廉价的一次性产品，而不是耐用品。为什么会出现这种情况？"
            "这是积极还是消极的发展？" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-two-practical-skills",
        "task_type": "task2",
        "question_type": "two_part",
        "difficulty": "easy",
        "tags": ["education", "family"],
        "prompt_text": (
            "Many students today lack basic practical skills such as cooking or managing "
            "money. Why is this the case? Should schools be responsible for teaching "
            "these skills?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "如今许多学生缺乏做饭、理财等基本生活技能。为什么会这样？学校是否应该负责教授这些技能？"
            + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-two-online-relationships",
        "task_type": "task2",
        "question_type": "two_part",
        "difficulty": "medium",
        "tags": ["media", "technology", "family"],
        "prompt_text": (
            "Nowadays many people communicate through social media instead of meeting in "
            "person. Why is this happening? Does it have a positive or a negative effect "
            "on relationships?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "如今许多人通过社交媒体交流，而不是见面。为什么会出现这种情况？"
            "它对人际关系的影响是积极的还是消极的？" + _T2_INSTRUCTIONS_ZH
        ),
    },
    {
        "key": "t2-two-science-careers",
        "task_type": "task2",
        "question_type": "two_part",
        "difficulty": "hard",
        "tags": ["science", "education", "work"],
        "prompt_text": (
            "In some countries, fewer young people are choosing careers in science and "
            "engineering. Why might this be happening? What can be done to encourage "
            "more students into these fields?\n\n" + _T2_INSTRUCTIONS
        ),
        "prompt_translation": (
            "在一些国家，选择科学和工程职业的年轻人越来越少。可能的原因是什么？"
            "可以做些什么鼓励更多学生进入这些领域？" + _T2_INSTRUCTIONS_ZH
        ),
    },
]
