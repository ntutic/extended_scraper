
# **Handy Scraping: framework for reusable and flexible routines**

## **Workflow**

The goal of this framework is to make scraping projects more easy to create, adjust, test, repair and deploy. It can handle scraping jobs using `requests` (get and post requests) or `selenium` (for instances where reaching the proper dynamic state is too tedious over requests (//todo necessary? replicating functionality over requests?)).

Note: This document mentions many features that have not (yet) been implemented (when followed by //todo). 

> `*.json` files `scrape/` contain routines for scraping, processing and/or storing data using sets of instruction
>    - they can call various inbuilt methods for handling processes;
>    - they can call other `*.json` files so projects can be broken into smaller components;
>    - they can be nested in other folders //todo

> `settings.json` from `scrape/` contains various default settings for scraping jobs
>    - this file contains default arguments that can be overwritten for specific jobs by including `settings` in their `*.json`
>    - `database` passes settings for data export //todo
>        - for SQL, connection data has to be provided. 
>        - for .csv, file-name suffix has to be provided. 

> `action.json` from `scrape/` contains named sets of routines to call //todo
>    - manually run pre-defined scraping jobs from CLI //todo
>    - automatically run various actions at predetermined schedules or conditional logic //todo
>    - they can call other `action__*.json` from parent folder (double underscore enforced) //todo
>    - `default.json` used when CLI includes no routine //todo

> `*.json` files in `scrape/__tests__/` contains routines and/or actions for validating data
>    - test can be asserted before running job or before updating database state //todo
>    - support for mock data //todo


### **Create**

In a `scrape/` folder, include a `settings.json` 


<details>
    <summary>Parameters for "scrape/settings.json"</summary>

> ***database_dictionary*** submitted under the form :

    {
        "sql": {
            "user": ${user},
            "password": ${password},
            "host": ${host},
            "database": ${database}
        },
        "csv: {
            "suffix": ${suffix}
        }
    }

> Optionally, nest a ***database_dictionary*** as an attribute of a **routine_dictionary** (detailed below), it will take precedence over a ***database_dictionary*** from "scrape/settings.json" (becomes optional)

</details>

<br/>


 created are stored in a ***selection_dictionary*** containing instructions for navigation,  :

<details>
    <summary>Parameters for "selection_dictionary"</summary>

> ***selection_dictionary*** submitted under the form :

    selection_dictionary = {
        "type": ${type},
        "sel": ${sel},
        "index": ${index},
        "child": {
            "type": ${type},
            "sel": ${sel,
            "attr": ${attr},
            "date_type": ${date_type},
            "slice": ${slice}
        }
    }

> An instance of a ***selection_dictionary*** contains the variables below.

### **Element selection** :
- **tag** : "a"/"div"/"li"/... (str) 

> If provided alone, returns all elements of tag. 

- **type** (opt): "id"/"class"/..., always with **sel** (str)
- **sel** (opt): value of element's type, always with **type** (str, int, float)

> If both provided, returns all elements of tag selected by attribute. 

- **index** (opt): single value or range to select from order retrieved (int, [int, int])

> If provided, elements or values retrieved are sliced index (0-indexed) or within range of indexexs ([min, max+1]).

- **child** (opt): nested element or attribute selection within parents (***selection_dictionary***)

> If provided, recursively returns all elements from *that* nested ***selection_dictionary*** by searching within elements of the current selection.

### **Value selection**  :

> None of these variables can be provided on the same level as a **child** nested ***selection_dictionary***. 

- **attr** (opt): "text" or **attr_type** (str)

> If provided, returns the text or the **attr**'s value as the attribute's name for selected elements.

- **date_type** (opt): format string for datetime [(source)](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes), always with **attr** (str)

> If provided, converts selected text values to datetime object using the given string format.
    
- **slice** (opt): slices result with min, max provided ([min, max])

</details>

<br/>

> For scraping, parameters and functions have to be provided under ***routine_dictionary*** that will be executed by the ***launcher*** :

<details>
    <summary>Parameters and functions for "scrape_settings_*.json"</summary>


> An instance of a ***routine_dictionary*** contains  a ***parameters_dictionary*** and one (dict) or more (list of dicts) ***function_dictionary*** - a list is executed in the order inserted and a function can be repeated by adding a unique digit in it's **function_name** (has to be a valid function found in "scrape_control.py"). It is stored under a unique **routine_name** in  "scrape_settings_*.json". The file can contain one or more ***routine***. 

> An instance of a ***routine_dictionary*** is submitted under the form :

    ${routine_name}: {
        "parameters": ${parameters_dictionary},
        "functions": [
            {
                ${function_name}: ${function_dictionary}
            }, ...
        ]
    }

> An instance of a ***parameters_dictionary*** is submitted under the form :

    "parameters": {
        "url": ${url},
        "first_page": ${first_page},
        "next_page": ${next_page},
        "path_out": ${path_out},
        "download_entry": {
            "url": ${url},
            "file_name": ${file_name}
        }
    }

> It can contain the variables :

- **url**: local (file or folder path) or online (http address) (str, [str])
- **first_page** (opt.): go to **url** value in element selected from original **url** request(***selection_dictionary***)
- **next_page** (opt.): loop over **url** value in element selected from current **url** request (***selection_dictionary***)
- **path_out** (opt.): relative or abs. path for downloaded outputs, if any (str)
- **download_entry** (opt.): contains dictionary with **url** and **file_name** variables (dict), always with **path_out**

> Instances of possible **function_name** & ***function_dictionary*** pairs are shown below, they can be provided in any order as a list. 

> **scrape_values**  retrieves a ***selection_dictionary*** from the every container found, stores them in an internal dictionary with their **value_name** for later use or export. They can be called upon from a variable  //todo verif whcih 
by adding a dot at the start of the string with it's **value_name**. 

    "scrape_values": [
        {
            "container": ${selection_dictionary}
            "values": [
                ${value_name}: ${selection_dictionary}, ...
            ]
        }, ...
    ]

> Retrieved values can be exported by calling the **entry_to_db** function.

    "entry_to_db": {
        "type": ${type},
        "table": ${table},
        "serial": "${serial},
        "fields": {
            "field_name": ${field_value}
        }
    } 

> It can contain one of these variables : 

- type: "sql" or "csv" (str)

> Will use the appropriate settings based on priority.

- table: name of table in database or in csv files to use (str)
- serial: fields that are continuation of last in table (**field_key**, [**field_key**, ...])
- fields: series of **field_key** and **field_value**

> Reminder **field_value** can retrieve values stored in **scrape_values()** with a string of the **field_name** preceded by a point.

</details>

</br>

> The ***launcher*** executed as a standalone will execute all routines. It can also be called with the arguments for specific files or routines.

<details>
    <summary>Parameters "scrape_launcher.py"</summary>

> Call the file with one or both following arguments, each holding a string or list of strings.

- **file_name** (opt.): name(s) of "scrape_settings_*.json" file(s) to execute.
- **routine_name** (opt.): name(s) of routines within file(s) to execute.

> Provide empty brackets for **file_name** if **routine_name** called alone.

</details>

***

## Example 1 : Scraping REIT properties to SQL

> ### We will retrieve property information from BTB REIT's portfolio.
###

> **1 :**
Create required tables in SQL database "reits".

<details>
    <summary>Show SQL database details</summary>

>Our "reits" database will have the following schema. The tables have to be present in the database.

![db_relational](./readme_img/btb_relational.PNG 'Schema')

</details>

<br/>

> **2 :**
Provide connection parameters in database_settings.json

<details>
    <summary>Show parameters dictionary.</summary>

    {
        "sql": {
            "user": "postgres",
            "password": "my_password",
            "host": "localhost",
            "database": "reits"
        }
    }


</details>

<br/>

> **3 :**
Retrieve selectors of needed elements from source page.

<details>
    <summary>Show elements used from source page.</summary>

![BTB REIT](./readme_img/btb_reit_elements.png 'BTB REIT elements')

</details>

<br/>

> **4 :**
Provide selectors in scrape_settings_demos.json as nested dictionary under "scrape_properties_BTB".

<br/>

>**5 :**
Run scrape_launcher.py to execute routine!

<details>
    <summary>Show results of routine.</summary>

> Listed properties have been stored in a table.

![BTB REIT elements](./readme_img/btb_reit_results.png 'BTB REIT elements')

> Their individual pages have been stored locally.

![BTB REIT properties](./readme_img/btb_reit_files.png 'BTB REIT fiels')

</details>

<br/>

> **6 :**
We can retrieve further data from the individual pages, we will scrape them locally by a new instructions dictionary under "scrape_properties_BTB" using the files' folder relative path as "url". 

<details>
    <summary>Show elements for additional details to scrape.</summary>

    Note: The "Leasing details" and "Building accessibility" containers show variable statistics. They will be stored in flexible "attribute" and "stat" tables. When a "title_*" variable is not an existing "stat", a new field will be created.

![BTB REIT details](./readme_img/btb_reit_details.png 'BTB REIT details')

</details>

<br/>

> **7 :**
After populating the instructions dictionary with these elements, we can launch "scrape_launcher.py" passing with the argument "scrape_properties_BTB" so that it doesn't run the first routine again. We could pass a list of routines as "['...', '...']".

<details>
    <summary>Show results of routine.</summary>

![BTB REIT elements](./readme_img/btb_reit_retails_results.png 'BTB REIT details results')

</details>



  c p
c 
p