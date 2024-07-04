import os
import yaml
import json
import requests
import sqlite3
from termcolor import colored

def load_config(file_path):
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
        for key, value in config.items():
            os.environ[key] = value

class SQLQueryGenerator:
    def __init__(self, model, db_path='my_database.db', verbose=False):
        load_config('config.yaml')
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.url = 'https://api.openai.com/v1/chat/completions'
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        self.model = model
        self.db_path = db_path
        self.verbose = verbose
        self.schema = self.extract_db_schema()

    def extract_db_schema(self):
        schema = {}
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get the list of tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            schema['tables'] = [table[0] for table in tables]

            # Get the columns for each table
            schema['columns'] = {}
            for table in schema['tables']:
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                schema['columns'][table] = [column[1] for column in columns]
            
            conn.close()
        except sqlite3.Error as e:
            print(colored(f"Error accessing database schema: {e}", 'red'))
        
        if self.verbose:
            print(colored(f"Database Schema: {schema}", 'yellow'))
        
        return schema

    def generate_sql_query(self, plan, query):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "generate_sql",
                    "description": "Generate SQL query based on the plan, user query, and database schema",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql_query": {
                                "type": "string",
                                "description": "The generated SQL query based on the plan, user query, and database schema"
                            },
                        },
                        "required": ["sql_query"]
                    }
                }
            }
        ]

        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": f"Query: {query}\n\nPlan: {plan}\n\nSchema: {self.schema}"}
            ],
            "temperature": 0,
            "tools": tools,
            "tool_choice": "required"
        }

        json_data = json.dumps(data)
        response = requests.post(self.url, headers=self.headers, data=json_data)
        response_dict = response.json()

        tool_calls = response_dict['choices'][0]['message']['tool_calls'][0]
        arguments_json = json.loads(tool_calls['function']['arguments'])
        sql_query = arguments_json['sql_query']
        print(colored(f"Generated SQL Query: {sql_query}", 'yellow'))

        return sql_query

    def execute_query(self, query):
        """
        Execute an SQL query on a database file and return the results.
        
        :param query: SQL query to execute
        :return: Query results
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()
            return results
        except sqlite3.Error as e:
            return f"An error occurred: {e}"

    def use_tool(self, plan=None, query=None):
        results_dict = {
            "query": query,
            "plan": plan
        }

        sql_query = self.generate_sql_query(plan, query)
        results_dict["sql_query"] = sql_query

        query_results = self.execute_query(sql_query)
        results_dict["query_results"] = query_results

        if self.verbose:
            print(colored(f"Results Dictionary: {results_dict}", 'yellow'))

        return results_dict

if __name__ == '__main__':
    generator=SQLQueryGenerator()
    generator.use_tool()
    # generator = SQLQueryGenerator(model="gpt-3.5-turbo", verbose=True)
    # results_dict = generator.use_tool(plan="Generate SQL query for procurement spend analysis", query="Show me a breakdown of our tail spend by category for the last quarter")
    # print(results_dict)
