"""IPL 2027 retention-day player status (17 Nov 2026), reconciled from the owner's
notes and published reports. Every entry carries its source; disagreements are kept
as explicit conflicts rather than resolved silently.

Sources
  OWNER   owner-supplied retention summary (17 Nov 2026)
  CT      CricTracker team-wise retention lists, 17 Nov 2026
  OUT     Outlook India retention live blog, 17 Nov 2026
  SC      SportsCafe released-players list, 17 Nov 2026
  CA      CricketAddictor MI retention list, 17 Nov 2026
  SG      Sunday Guardian / MyKhel MI retention lists, 17 Nov 2026
"""

AUCTION = {"date": "16 Dec 2026", "venue": "Goa", "salary_cap_cr": 157.0}

PURSE = {  # crore, slots, overseas slots (OWNER; matches OUT and CT for RR)
    "Lucknow Super Giants": (47.45, 7, 3), "Kolkata Knight Riders": (41.65, 8, 3),
    "Sunrisers Hyderabad": (40.15, 7, 3), "Delhi Capitals": (39.50, 9, 4),
    "Mumbai Indians": (32.60, 9, 2), "Chennai Super Kings": (28.05, 6, 2),
    "Rajasthan Royals": (27.05, 6, 3), "Punjab Kings": (18.60, 6, 2),
    "Royal Challengers Bengaluru": (14.15, 5, 1), "Gujarat Titans": (8.75, 3, 2),
}

# ---------------------------------------------------------------- retained / traded in
RETAINED = {
    "Rajasthan Royals": [  # CT full list (17) + confirmed trades in
        "Shubham Dubey", "Donovan Ferreira", "Yashasvi Jaiswal", "Aman Rao Perala", "Lhuan Pretorius",
        "Yash Punja", "Dasun Shanaka", "Vaibhav Sooryavanshi", "Jofra Archer", "Ravi Bishnoi",
        "Nandre Burger", "Sushant Mishra", "Brijesh Sharma", "Sandeep Sharma", "Riyan Parag",
        "Ravindra Jadeja", "Dhruv Jurel", "Mohammed Shami", "Manimaran Siddharth"],
    "Chennai Super Kings": [
        "Ruturaj Gaikwad", "Sanju Samson", "Shivam Dube", "Ayush Mhatre", "Dewald Brevis", "Noor Ahmad",
        "Liam Livingstone", "Jack Edwards", "Anshul Kamboj", "Jamie Overton", "Urvil Patel",
        "Gurjapneet Singh", "Shreyas Gopal", "Mukesh Choudhary", "Kartik Sharma"],
    "Mumbai Indians": [
        "Jasprit Bumrah", "Suryakumar Yadav", "Rohit Sharma", "Tilak Varma", "Arshdeep Singh",
        "Ryan Rickelton", "Corbin Bosch", "Ashwani Kumar", "Naman Dhir", "Will Jacks", "Mitchell Santner",
        "Robin Minz", "Shardul Thakur", "Quinton de Kock"],
    "Royal Challengers Bengaluru": [
        "Virat Kohli", "Rajat Patidar", "Phil Salt", "Tim David", "Josh Hazlewood", "Bhuvneshwar Kumar",
        "Krunal Pandya", "Jitesh Sharma", "Venkatesh Iyer", "Devdutt Padikkal", "Rasikh Salam",
        "Romario Shepherd", "Suyash Sharma"],
    "Kolkata Knight Riders": [
        "Cameron Green", "Rinku Singh", "Sunil Narine", "Varun Chakravarthy", "Harshit Rana",
        "Angkrish Raghuvanshi", "Finn Allen", "Ramandeep Singh", "Vaibhav Arora", "Anukul Roy"],
    "Sunrisers Hyderabad": [
        "Pat Cummins", "Heinrich Klaasen", "Abhishek Sharma", "Ishan Kishan", "Nitish Kumar Reddy",
        "Eshan Malinga", "Aniket Verma", "Smaran Ravichandran", "T Natarajan", "Khaleel Ahmed", "Nathan Ellis"],
    "Delhi Capitals": [
        "Rishabh Pant", "KL Rahul", "Axar Patel", "Tristan Stubbs", "David Miller", "Lungi Ngidi",
        "Mukesh Kumar", "Ashutosh Sharma", "Vipraj Nigam", "Sameer Rizvi", "Auqib Nabi", "Zeeshan Ansari"],
    "Gujarat Titans": [
        "Shubman Gill", "Sai Sudharsan", "Rashid Khan", "Jos Buttler", "Mohammed Siraj", "Kagiso Rabada",
        "Prasidh Krishna", "Washington Sundar", "Jason Holder", "Rahul Tewatia", "Harshal Patel",
        "Sai Kishore", "Glenn Phillips", "Arshad Khan", "Manav Suthar"],
    "Punjab Kings": [
        "Shreyas Iyer", "Hardik Pandya", "Shashank Singh", "Prabhsimran Singh", "Marcus Stoinis",
        "Marco Jansen", "Yuzvendra Chahal", "Priyansh Arya", "Cooper Connolly", "Azmatullah Omarzai",
        "Harpreet Brar", "Vijaykumar Vyshak"],
    "Lucknow Super Giants": [
        "Nicholas Pooran", "Mitchell Marsh", "Aiden Markram", "Josh Inglis", "Kuldeep Yadav", "Sam Curran",
        "Mayank Yadav", "Mohsin Khan", "Ayush Badoni", "Digvesh Rathi", "Prince Yadav", "Abdul Samad"],
}

# ---------------------------------------------------------------- released (2026 team)
RELEASED = {
    "Rajasthan Royals": ["Shimron Hetmyer", "Tushar Deshpande", "Adam Milne", "Kwena Maphaka", "Emanjot Chahal",
                         "Kuldeep Sen", "Ravi Singh", "Vignesh Puthur", "Yudhvir Singh"],
    "Chennai Super Kings": ["Mahendra Singh Dhoni", "Prashant Veer", "Matthew Short", "Matt Henry", "Zakary Foulkes",
                            "Aman Khan", "Kuldip Yadav", "Akash Madhwal", "Dian Forrester", "Macneil Noronha"],
    "Mumbai Indians": ["Trent Boult", "Deepak Chahar", "Allah Ghazanfar", "Keshav Maharaj", "Atharva Ankolekar",
                       "Mohammed Izhar", "Danish Malewar", "Mayank Markande", "Mayank Rawat"],
    "Royal Challengers Bengaluru": ["Jacob Bethell", "Mangesh Yadav", "Richard Gleeson", "Satwik Deswal", "Vihaan Malhotra"],
    "Kolkata Knight Riders": ["Matheesha Pathirana", "Mustafizur Rahman", "Rachin Ravindra", "Ajinkya Rahane",
                              "Akash Deep", "Blessing Muzarabani", "Rahul Tripathi", "Umran Malik", "Navdeep Saini",
                              "Luvnith Sisodia", "Tejasvi Singh", "Daksh Kamra"],
    "Sunrisers Hyderabad": ["Travis Head", "Gerald Coetzee", "Jaydev Unadkat", "Kamindu Mendis", "Dilshan Madushanka",
                            "Shivam Mavi", "David Payne", "Onkar Tarmale", "Amit Kumar"],
    "Delhi Capitals": ["Mitchell Starc", "Nitish Rana", "Abishek Porel", "Pathum Nissanka", "Ben Duckett", "Karun Nair",
                       "Dushmantha Chameera", "Kyle Jamieson", "Rehan Ahmed", "Sahil Parakh", "Ajay Mandal"],
    "Gujarat Titans": ["M Shahrukh Khan", "Ishant Sharma", "Luke Wood", "Kulwant Khejroliya", "Connor Esterhuizen"],
    "Punjab Kings": ["Nehal Wadhera", "Lockie Ferguson", "Mitchell Owen", "Xavier Bartlett", "Pyla Avinash",
                     "Praveen Dubey", "Vishal Nishad"],
    "Lucknow Super Giants": ["Avesh Khan", "Anrich Nortje", "Wanindu Hasaranga", "Matthew Breetzke", "George Linde",
                             "Naman Tiwari", "Arshin Kulkarni"],
}

NOTES = {  # player -> (flag, note)
    "Allah Ghazanfar": ("conflict", "Reported released by CricketAddictor, CricToday and SportsCafe; listed as retained by "
                                    "Sunday Guardian and MyKhel. Treat as available only once the official IPL list confirms it."),
    "Ravi Bishnoi": ("conflict", "Owner notes list him under LSG; CricTracker's RR list (17 Nov) has him retained by RR at ₹7.20 Cr. RR list used."),
    "Abdul Samad": ("conflict", "Conflicting live-ticker reports on retention by LSG."),
    "Travis Head": ("availability", "Released; reports say he may prioritise Australia's schedule and miss IPL 2027."),
    "Mitchell Starc": ("availability", "Released; reports say he may opt out of IPL 2027."),
    "Ajinkya Rahane": ("retired", "Retired from the IPL."),
    "Mahendra Singh Dhoni": ("retired", "Retired as a player; CSK mentor."),
    "Xavier Bartlett": ("conflict", "In owner notes as a PBKS release; not in the SportsCafe PBKS list."),
    "Luke Wood": ("conflict", "Owner notes say Luke Wood; Outlook's list says Mark Wood."),
}

LAST_CONTRACT_CR = {  # last IPL contract value, where published (OUT / CT big-release lists)
    "Matheesha Pathirana": 18.0, "Travis Head": 14.0, "Trent Boult": 12.5, "Mitchell Starc": 11.75,
    "Shimron Hetmyer": 11.0, "Deepak Chahar": 9.25,
}

ALIASES = {  # dataset name for names spelled differently in reports
    "Aman Rao Perala": "Aman Rao Perala", "Lhuan Pretorius": "Lhuan Pretorius", "Varun Chakravarthy": "Varun Chakravarthy",
    "T Natarajan": "Thangarasu Natarajan", "Tilak Varma": "Namboori Tilak Varma",
}
