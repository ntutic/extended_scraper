import requests
from bs4 import BeautifulSoup
import psycopg2
import time
import os
from datetime import datetime
import json
import sys

class ScrapeControl:
    def __init__(self):
        """
        Reusable and flexible scraping routines

        Execute script with the launch() method ond an ScrapeControl() instance 
        or from CLI, with or without arguments.

        See README.md for usage.

        """

        self.path_jobs = 'scrape/'

        # To monitor request load
        self.last_request = datetime.now()

        # Load output settings from mandatory file
        try:
            with open(self.path_jobs + "database_settings.json", "r") as f:
                self.db_settings = json.load(f)
        except FileNotFoundError:
            assert False, 'Error: file not found "scrape/settings.json".'
        

    def launch(self, files='', routines='', argv=''):
        """
        Method will execute requested routines, can be called from CLI as well.
        Calling it without any files, routines or CLI arguments will execute 
        every routine in every "*.json" file from the "scrape/" folder (except settings.json).
        """

        # Stores files/routines from CLI arguments in lists
        if argv:
            self.check_argv(sys.argv)

        # Stores files/routines from method arguments in lists
        elif files and routines:
            if isinstance(files, str):
                self.scrape_files = [files]
            elif isinstance(files, list):
                self.scrape_files = files

            if isinstance(routines, str):
                self.scrape_routines = [routines]
            elif isinstance(routines, list):
                self.scrape_routines = routines

        # Stores files/routines as empty lists, selecting every files/routines
        else:
            self.scrape_routines = []
            self.scrape_files = []

        assert isinstance(self.scrape_files, list) and isinstance(self.scrape_routines, list), "Error: wrong routine or file given"
        
        # Get local files to list, filtered by self.scrape_files and nomenclature
        files = [f for f in os.listdir('.') if os.path.isfile(f)]
        if self.scrape_files:
            files = [f for f in files if f in self.scrape_files]
        files = [f for f in files if 'settings' in f and f.split('.')[-1] == 'json']

        # We go over every file's instructions
        for file in files:
            with open(file) as f:
                dic = json.load(f)

            # We go over every routines in files, filtered by self.scrape_routines
            for name, routine in dic.items():
                if self.scrape_routines and name not in self.scrape_routines:
                    continue

                # We execute every routine
                print('Running: ' + name)
                self.run(routine, name)



    def run(self, routine, routine_name):
        """
        Method executes a routine, calling functions in the order inserted. 
        """

        assert 'parameters' in routine.keys(), "Error: parameters dict not found in rountine."
        self.parameters = routine['parameters']

        # Verify inputs in parameters
        for mandatory_parameter in ['url']:
            assert mandatory_parameter in self.parameters.keys(), "Error: '" + mandatory_parameter + "' not found in dict's parameters."

        # Store path for downloaded pages
        if 'path_out' in self.parameters.keys() and self.parameters['path_out'][-1] not in ['/', '\\']:
            self.parameters['path_out'] += '/' 
        self.path_out = self.parameters['path_out']

        # Create folder if absent
        if not os.path.exists(self.path_out):
            os.mkdir(self.path_out)

        # Store url or urls in parameters as list
        if not isinstance(self.parameters['url'], list):
            self.urls = [self.parameters['url']]
        else:
            self.urls = self.parameters['url']

        # Prepare database based on settings priority
        if "settings" in self.parameters.keys():
            db_settings_dic = self.parameters['settings']
            db_settings_type = self.parameters['database']
        elif routine_name in self.db_settings.keys():
            assert isinstance(self.db_settings[routine_name], dict), 'Error: not dict for routine in database_setting.json'
            db_settings_dic = self.db_settings[routine_name][self.parameters['database']]
            db_settings_type = self.parameters['database']
        else:
            db_settings_dic = self.db_settings[self.parameters['database']]
            db_settings_type = self.parameters['database']
        self.database_setup(db_settings_type, db_settings_dic)

        # Get landing page
        for url in self.urls:
            self.url = url

            # Default requests as 'get' #//TODO requesting post may not work ATM
            if 'request' in self.parameters.keys():
                request_type = self.parameters['request']
            else:
                request_type = 'get'

            # Execution logic for 'get'
            if request_type == 'get':
                self.soup = self.get_request('get', self.url)
                    
                # Bounce from initial soup with 'first_page' dictionary selecting a new url.
                if 'first_page' in self.parameters.keys():
                    url_new = self.get_elements(self.parameters['first_page'])
                    
                    # Presently useless, mostly //TODO
                    if 'optional' in self.parameters['first_page'].keys():
                        optional = self.parameters['first_page']['optional']
                    else: 
                        optional = True

                    # Processs new url if found
                    if url_new:
                        url = self.parse_url(self.url, url_new)
                        assert isinstance(url, str) and url, 'Error: Empty url provided for first page'
                        # //TODO validate
                        
                        # Store cleaned news url as base url and get new request
                        self.url = url
                        self.soup = self.get_request('get', self.url)

                    # If no new url yielded
                    else:
                        assert optional, 'Error: no url_new while non-optional, add parameter or verify'

            # //TODO add post request logic
            elif request_type  == 'post':
                assert 'payload' in self.parameters.keys(), 'Error: no payload for post request'
                self.soup = self.get_request('post', self.url, payload=self.parameters['payload'])
                

            # Iterate over pages to scrape until no "next_page" url yielded
            while_continue = True
            while while_continue:
                    
                # Iterate over functions and call them
                for fc_name, fc_args in routine['functions'].items():

                    # To support repetition of function, needs unique digit in name
                    fc = ''.join([c for c in fc_name if not c.isnumeric()])

                    # Call function with arguments provided           
                    getattr(self, fc)(fc_args)

                # Keep looping while 'next_page' yields a new url 
                if 'next_page' in self.parameters.keys():

                    # Post request logic #//TODO fix/do
                    if request_type == 'post':
                        page_value = self.parameters['payload'][self.parameters['next_page']['payload']]
                        next_page_value = page_value + 1
                        if next_page_value > self.parameters['next_page']['max']:
                            while_continue = False
                            continue
                        self.parameters['payload'][self.parameters['next_page']['payload']] = next_page_value
                        self.soup = self.get_request('post', self.url, payload=self.parameters['payload'])

                    # Get request logic
                    elif request_type == 'get':

                        # Convert to list (of len=1) if single dictionary
                        if isinstance(self.parameters['next_page'], dict):
                            self.parameters['next_page'] = [self.parameters['next_page']]
                        
                        # Get new url from every selection_dictionary provided, until non is yielded 
                        for element_i, element_dic in enumerate(self.parameters['next_page']):
                            
                            # //TODO check logic
                            if 'optional' in element_dic.keys():
                                optional = element_dic['optional']
                            else: 
                                optional = False
                            
                            # Update url, //TODO merge with first_page and expand url parsing
                            url_new = self.get_elements(element_dic)
                            if url_new:
                                url = self.parse_url(self.url, url_new)
                                if url:
                                    self.url = url
                                    self.soup = self.get_request('get', self.url)
                                    break
                            elif not url_new and element_i == len(self.parameters['next_page']) - 1:
                                #assert optional, 'Error: non-optional url_new empty in next_page'
                                while_continue = False
                
                # Don't loop without 'next_page' instruction
                else:
                    while_continue = False
                    

    def check_argv(self, argv):
        """
        Parse CLI arguments provided and stores appropriate lists in 
        storage attributes (self.scrape_files and self.scrape_routines)
        """
        # Only first arg (files) provided
        if len(argv) in [2]:
            self.scrape_files = argv[1]
            self.scrape_routines = []

        # Both args provided
        elif len(argv) in [3]:
            self.scrape_files = argv[1]
            self.scrape_routines = argv[2]

        # No args provided, returns empty list
        else:
            self.scrape_files = []
            self.scrape_routines = []
            return

        # Converts str to list
        if self.scrape_files and isinstance(self.scrape_files, str):
            if len(self.scrape_files) > 1 and self.scrape_files[0] == ['['] and self.scrape_files[1] == [']'] :
                self.scrape_files = eval(self.scrape_files)
            else:
                self.scrape_files = [self.scrape_files]

        # Converts str to list
        if self.scrape_routines and isinstance(self.scrape_routines, str):
            if len(self.scrape_routines) > 1 and self.scrape_routines[0] == ['['] and self.scrape_routines[1] == [']'] :
                self.scrape_routines = eval(self.scrape_routines)
            else:
                self.scrape_routines = [self.scrape_routines]


    def database_setup(self, db_type, db_settings=''):
        """
        Initialize ways of outputting scraped data. 
        Passing it a settings dictionary over-rides priority. 
        """
        assert db_type in ['sql', 'csv'], "Error: '" + db_type + "' for database not 'sql' or 'csv'"


        # //TODO check for prio?
        if not db_settings:
            db_settings = self.db_settings[db_type]

        # Connect to SQL database
        if db_type == 'sql':
            try:
                self.conn = psycopg2.connect(        
                    host=db_settings['host'],
                    database=db_settings['database'],
                    user=db_settings['user'],
                    password=db_settings['password']
                )
                
                self.cur = self.conn.cursor()          

            except psycopg2.OperationalError as err:
                err_arg = err.args[0].split('FATAL:  ')[1].split(' ')[0]
                print("Couldn't connect to database: " + err_arg)
                exit()

        # Prepare folder and variables for .csv files to output
        if db_type == 'csv':
            pass #//todo implement


    def get_request(self, type_req, url, payload='', headers='', limiter=2):
        """
        Returns soup of requested url. Limits requests per second to limiter.
        //TODO Add/finish post details, probably doesn't work ATM
        """
        assert type_req.lower() in ['get', 'post'], "Error: '" + type_req.lower() + "' request not 'get' or 'post'."
        assert isinstance(url, str) and len(url) > 3 and '.' in url, "Error: invalid url '" + url + "'"
        
        # Read local files
        if '.html' == url[-5:]:
            with open(url, encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'lxml')

        else:
            #//TODO CHeck up
            if 'headers' in self.parameters.keys():
                headers = self.parameters['headers']
            else:
                headers = {}

            # Max 1 request per limiter seconds
            delta = datetime.now() - self.last_request
            if delta.seconds < limiter:
                time.sleep(2 - delta.total_seconds())

            # Payload for post
            if isinstance(payload, dict):
                response = getattr(requests, type_req.lower())(url, headers=headers, data=payload) #//todo VALIDATE
            else:
                response = getattr(requests, type_req.lower())(url, headers=headers)

            assert response.status_code == 200, "Error: Status code " + str(response.status_code) + " of request"
            #//TODO add contingencies
            
            # Get requested soup
            soup = BeautifulSoup(response.content, 'lxml') #//TODO save as pickle?
        
        return soup


    def get_elements(self, element_dic, soup='', results=''):
        """
        Returns elements or values (attribute or text of elements). Searches within soup if provided, else from self.soup.
        Results used for recursive search.. 
        """

        assert 'tag' in element_dic.keys() or 'attr' in element_dic.keys(), "Error: Mandatory 'tag' not found in 'get_elements()'s dic."
        
        # Make results to empty list on first root function call
        if not isinstance(results, list):
            results = []

        # Assign base soup if none provided
        if not soup:
            soup = self.soup

        # Return elements if tag provided with attribute selector
        if "tag" in element_dic.keys() and "type" in element_dic.keys() and "sel" in element_dic.keys():
            tags = soup.find_all(element_dic['tag'], {element_dic['type']: element_dic['sel']})
        
        # Return elements if tag provided alone
        elif "tag" in element_dic.keys():
            tags = soup.find_all(element_dic['tag'])

        # Return soup as single tag otherwise //TODO for what alrdy?
        else:
            tags = [soup]

        # Slice tags by index if provided
        if "index" in element_dic.keys():
            assert isinstance(element_dic['index'], int) or isinstance(element_dic['index'], list), "Error: index not int or list not found in 'get_elements()'s dic."

            # Get single tag in list
            if isinstance(element_dic['index'], int):
                tags = [tags[element_dic['index']]]

            # Get range of tags in list
            elif isinstance(element_dic['index'], list):
                assert len(element_dic['index']) == 2, "Error: index list not with 2 values [min, max]."
                tags = tags[element_dic['index'][0]:element_dic['index'][1]]

        # Iterate over tags
        for tag in tags:

            # If 'child' present, recursively call present function.
            # Will push results from deepest node/child to root function call
            if 'child' in element_dic.keys():
                results = self.get_elements(element_dic['child'], soup=tag, results=results)
                break

            # Return text or attribute if requested
            elif 'attr' in element_dic.keys():
                if 'text' == element_dic['attr']:
                    result = tag.text
                else:
                    result = tag[element_dic['attr']]

            # Return original tag otherwise
            else:
                result = tag

            # Return result (if str) sliced
            if 'slice' in element_dic.keys():
                assert isinstance(result, str), 'Error: Tried to slice non-str'
                result = result[element_dic['slice'][0]:element_dic['slice'][1]]
            
            # Returns result re-interpreted by 'date_type' format string
            if "date_type" in element_dic.keys():
                assert isinstance(result, str), "Error: date to parse is'" + type(result) + "' not str."
                result = datetime.strptime(result.strip(), element_dic['date_type'])
            
            # Add processed tag to results
            results.append(result)

        # Returns results (to itself or root call)
        return results


    def parse_url(self, url, url_new):
        """
        Parses url based on some rules for this project to retrieve usable url link from full url, 
        partial url from root, arguments to current url, local html file path, folder of html files path.
        """

        # Make url to list, //todo useful? or should be reversed?
        if isinstance(url_new, str):
            url_new = [url_new]
        else:
            assert isinstance(url_new, list) and len(url_new) == 1, 'Error first page selection, '
        url_new = url_new[0]

        # If new url is arguments starting from ?, adding it to root url
        if url_new[0] == '?':
            url = url.split('?')[0] + url_new

        # If new url starts with a slash, getting local file
        elif url_new[0] in ['/', '\\']:
            root = '.'.join(url.split('.')[:-1]) + '.' + url.split('.')[-1].split('/')[0].split('\\')[0]
            url = root + url_new

        # If new url starts and ends with a slash, getting list of files
        #//todo implement logic
        elif url_new[0] in ['/', '\\'] and url_new[-1] in ['/', '\\']:
            root = '.'.join(url.split('.')[:-1]) + '.' + url.split('.')[-1].split('/')[0].split('\\')[0]
            url = root + url_new

        # Otherwise return original new url
        else:
            url = url_new
    
        return url



    def download_page(self, dic, results=''):
        """
        Locally downloads provided url under provided file_name
        """
        #//todo unnecessary?
        dic = dic.copy()

        # Converts referenced fields to stored variables //todo add more logic, dump in one method
        for key in ['url', 'file_name']:
            if isinstance(dic[key], str) and dic[key][0] == '.':
                dic[key] = results[dic[key][1:]]
            
        # Retrieve page soup
        url = self.parse_url(self.url, url_new=dic['url'])
        soup = self.get_request('get', url)

        # Locally save page
        filename = str(dic['file_name']) + ".html"
        with open(self.parameters['path_out'] + filename, 'w',  encoding="utf-8") as f:            
            f.write(str(soup))


    def scrape_values(self, dic):
        """
        Retrieves requested values to local dictionary
        """
        assert isinstance(dic, dict), "Error: " + type(dic) + " provided to 'scrape_values()' instead of dict"
        
        # //todo maybe unnecessary
        dic = dic.copy()

        # Retrieving containers
        containers = self.get_elements(dic['containers'])
        assert containers, 'Error: no containers'
        del dic['containers']

        # We'll iterate over containers and dump results in self.scrape_results under it's container id
        self.scrape_results = {}
        for container_i, container in enumerate(containers):
            self.scrape_results[container_i] = {}

            # Get values requested
            for value_name, element_dic in dic['values'].items():

                # Adds current count to len of present table //todo implement
                if element_dic == 'serial':
                    self.scrape_results[container_i][value_name] = container_i

                # Returns requested elements
                else:
                    assert isinstance(element_dic, dict), "Error: " + type(element_dic) + " provided to 'scrape_values()' instead of dict"
                    results = self.get_elements(element_dic, soup=container)
                    if isinstance(results, list) and len(results) == 1: #//TODO check ==1
                        results = results[0]

                    # Stores results
                    self.scrape_results[container_i][value_name] = results


    def entry_to_db(self, dic):
        """
        Send scraped values to database for storage.
        """
        assert isinstance(dic, dict), "Error: " + type(dic) + " provided to 'entry_to_db()' instead of dict"
        #//todo validation

        # Logic for sql
        if self.parameters['database'] == 'sql':
            
            # Get table and length
            table = dic['table'] 
            self.cur.execute('SELECT * from ' + table + ';')
            table_len = len(self.cur.fetchall())

            # Increment serial count to table's length
            if "serial" in dic.keys():
                if isinstance(dic['serial'], str):
                    dic['serial'] = [dic['serial']]
            else:
                dic['serial'] = []
            
            # Iterate over entries 
            for entry_i, entry_dic in self.scrape_results.items():
                #//TODO implement logic for nested vars, query vars

                # Iterate over requested fields
                fields = []
                values = []
                for field, value in dic['fields'].items():

                    # Null values
                    if isinstance(value, str) and not value:
                        value = 'NULL'

                    # Stored variable //todo add multi-level capability
                    elif isinstance(value, str) and value[0] == '.':
                        value = entry_dic[value[1:]]

                    # Convert datetime field to sql-readable date
                    if isinstance(value, datetime):
                        value = datetime.strftime(value, '%Y-%m-%d')

                    # Increment serial count to table's length
                    if field in dic['serial']:
                        value = int(value) + table_len + 1
                        self.scrape_results[entry_i][dic['fields'][field][1:]] = value

                    # Format numbers as str for sql query
                    if isinstance(value, int) or isinstance(value, float) or isinstance(value, str) and value.isnumeric():
                        value = str(value)

                    # Format values requiring apostrophes for sql 
                    elif isinstance(value, str) and value != 'NULL':
                        if field in ['href', 'url']:
                            value = self.parse_url(self.url, value)
                        value = value.strip()
                        value = value.replace("'", ' ')
                        value = "'" + value + "'"
                    
                    # To list for forming query
                    fields.append(field)
                    values.append(value)

                # To comma-separated string for query
                fields = ', '.join(fields)
                values = ', '.join(values)

                # Execute insertion query
                sql = 'INSERT INTO ' + table + ' (' + fields + ') VALUES (' + values + ');'
                self.cur.execute(sql)
                self.conn.commit()
                #//todo implement error controls
                
                # Download url locally if requested
                if 'download_entry' in self.parameters.keys():
                    self.download_page(self.parameters['download_entry'], results=entry_dic)

        # Logic for csv //TODO implement
        if self.parameters['database'] == 'csv':
            pass


# Execute when file launched, passes on arguments
if __name__ == "__main__":
    ctrl = ScrapeControl()
    ctrl.launch(argv=sys.argv)

    





            


            
            