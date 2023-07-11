def get_example(example_key: str) -> str:
    return example_pool[example_key]

example_pool = {
    'example1': """
### Example: An output template with If-condition instruction structure

```yaml
task: "Get current weather data for San Francisco and provide suggestions based on temperature, save the results to file"

objective:  # AI-generated objective content, wrapped in quotes

thoughts:  # AI-generated thoughts content, should be plain text without newlines, wrapped in quotes

hints_from_user:  # A list of hints from the user, each item must be plain text and wrapped in quotes

start_seq: 1  # user-specified start_seq

instructions:
  - seq: 1
    type: WebSearch
    inside_loop: false
    objective: "Find URLs related to current weather in San Francisco"
    rule_num: 2
    args:
      query: "temperature in San Francisco"
      save_to: "search_result_urls.seq1.list"

  - seq: 2
    type: Fetch
    inside_loop: false
    rule_num: 2
    objective: "Fetch the content from the first URL from the search results"
    args:
      url: "jvm.eval(jvm.get('search_result_urls.seq1.list')[0])"  # make sure the reference key exists.
      save_to: "fetched_content.seq2.str" # without <idx> as not inside a loop

  - seq: 3
    type: TextCompletion
    inside_loop: false
    objective: "Get the current temperature in San Francisco from the fetched content"
    rule_num: 3
    args:
      command: "Get the current temperature and url in San Francisco"
      output_fmt:
        kvs:
          - key: "temperature.seq3.int"  # without <idx> as not inside a loop
            value: "<to_fill>"
          - key: "source_url.seq3.str"
            value: "<to_fill>"
      content: "jvm.eval(jvm.get('fetched_content.seq2.str'))"

  - seq: 4
    type: If
    inside_loop: false
    objective: Evaluate condition to decide if we recommend outdoor or indoor activities
    rule_num: 5
    args:
      condition: "20 < jvm.eval(jvm.get('temperature.seq3.int')) < 30"
    then:
      - seq: 5
        type: TextCompletion
        inside_loop: false
        objective: "Generate outdoor activities suggestions"
        rule_num: 3
        args:
          command: "What outdoor activities should we recommend to the users? Please generate a weather notes"
          output_fmt:
            kvs:
              - key: "weather_notes.seq5.str"
                value: "<to_fill>"
          content: "Today's temperature in San Francisco is jvm.eval(jvm.get('temperature.seq3.int'))"
    else:
      - seq: 6
        type: TextCompletion
        inside_loop: false
        objective: "Generate indoor activities suggestions"
        rule_num: 3
        args:
          command: "What indoor activities should we recommend to the users? Please generate a weather notes"
          output_fmt:
            kvs:
              - key: "weather_notes.seq6.str"
                value: "<to_fill>"
          content: "Today's temperature in San Francisco is jvm.eval(jvm.get('temperature.seq3.int'))"

  - seq: 7
    type: TextCompletion
    inside_loop: false
    objective: "Generate a complete weather report for San Francisco using the gathered information"
    rule_num: 3
    args:
      command: "Please generate current weather report for San Francisco"
      output_fmt:
        kvs:
          - key: "weather_report.seq7.str"
            value: "<to_fill>"
      content: "temperature: jvm.eval(jvm.get('temperature.seq3.int')), source_url: jvm.eval(jvm.get('source_url.seq3.str')), weather_notes: jvm.eval(jvm.get('weather_notes.seq5.str') or jvm.get('weather_notes.seq6.str'))"

  - seq: 8
    type: RunPython
    inside_loop: false
    objective: "Save report to a file"
    rule_num: 5 # RunPython is the only instruction that can do file IO
    args:
      code: |
        with open('weather_report.txt', 'w') as f:
          f.write(jvm.get('weather_report.seq7.str'))
      code_review: "the code writes the weather report to a file named weather_report.txt"  # reviews the python code
      pkg_dependencies: []

end_seq: 8

overall_outcome: "The current weather report for San Francisco stored, it can be retrieved by jvm.eval(jvm.get('WeatherReport.seq7.str')) or file weather_report.txt, the report includes the source url of weather data, notes on suggestions from AI"
```
""",
    'example2': """
### Example: An output template with Loop instruction structure

```yaml
task: "Conduct research on the internet for AI-related news and write a blog"

objective:  # AI-generated objective content, wrapped in quotes

thoughts:  # AI-generated thoughts content, should be plain text without newlines, wrapped in quotes

hints_from_user:  # A list of hints from the user, each item must be plain text and wrapped in quotes

start_seq: 1  # user-specified start_seq

instructions:
  - seq: 1
    type: WebSearch
    inside_loop: false
    objective: "Find URLs related to recent AI news"
    rule_num: 2
    args:
      query: "recent AI news"
      save_to: "news_urls.seq1.list"

  - seq: 2
    type: Loop
    inside_loop: false
    objective: "Loop through the top 5 URLs to fetch and summarize the news"
    rule_num: 1
    args:
      count: "5"  # we want 5 news articles for the blog
      idx: "jvm.eval(jvm.get('idx'))"
      instructions:
        - seq: 3
          type: Fetch
          inside_loop: true
          objective: "Fetch the content from the current URL from the search results"
          rule_num: 2
          args:
            url: "jvm.eval(jvm.get('news_urls.seq1.list')[jvm.get('idx')])"
            save_to: "jvm.eval('news_content_' + str(jvm.get('idx')) + '.seq3.str')"  # with <idx> as inside a loop

        - seq: 4
          type: TextCompletion
          inside_loop: true
          objective: "Extract and summarize the key information from the fetched news content"
          rule_num: 3
          args:
            command: "Extract and summarize the key points from the AI news"
            output_fmt:
              kvs:
                - key: "jvm.eval('news_summary_' + str(jvm.get('idx')) + '.seq4.str')"  # with <idx> as inside a loop
                  value: "<to_fill>"
            content: "jvm.eval(jvm.get('news_content_' + str(jvm.get('idx')) + '.seq3.str'))"

  - seq: 5
    type: TextCompletion
    inside_loop: false
    objective: "Generate the blog content using the summarized news"
    rule_num: 4  # Use TextCompletion instead of Loop when combining a list of multiple news summaries into a single blog post.
    args:
      command: "Structure the blog post using the summaries of the news"
      output_fmt:
        kvs:
          - key: "blog_content.seq5.str"
            value: "<to_fill>"
      content: "jvm.eval('\\n'.join(jvm.list_values_with_key_prefix('news_summary_')))"

end_seq: 5

overall_outcome: "A blog post summarizing the latest AI news has been created, it can be retrieved by jvm.eval(jvm.get('blog_content.seq5.str'))"
```
""",
    'example3': """
### Example: An output template with Loop and If structure

```yaml
task: "Fetch the titles of the top 5 articles on Hacker News and decide whether to post them to a Slack channel"

objective: "Retrieve the titles of the top 5 articles on Hacker News and based on their relevance to AI, decide whether to post them to a Slack channel"

thoughts: "This task requires fetching the article titles from Hacker News and then making a decision for each title. Therefore, the instructions `WebSearch`, `Fetch`, `TextCompletion`, `If`, and `Loop` will be utilized."

hints_from_user: []

start_seq: 1

instructions:
  - seq: 1
    type: WebSearch
    inside_loop: false
    objective: "Find URLs of the top 5 articles on Hacker News"
    rule_num: 2
    args:
      query: "top 5 articles on Hacker News"
      save_to: "article_urls.seq1.list"

  - seq: 2
    type: Loop
    inside_loop: false
    objective: "Loop through the URLs to fetch the titles and decide whether to post to Slack"
    rule_num: 1
    args:
      count: "5"
      idx: "jvm.eval(jvm.get('idx'))"
      instructions:
        - seq: 3
          type: Fetch
          inside_loop: true
          objective: "Fetch the title from the current URL"
          rule_num: 2
          args:
            url: "jvm.eval(jvm.get('article_urls.seq1.list')[jvm.get('idx')])"
            save_to: "jvm.eval('article_title_' + str(jvm.get('idx')) + '.seq3.str')"

        - seq: 4
          type: TextCompletion
          inside_loop: true
          objective: "Decide if the article is relevant to AI"
          rule_num: 3
          args:
            command: "Determine if the article is about AI"
            output_fmt:
              kvs:
                - key: "jvm.eval('is_relevant_' + str(jvm.get('idx')) + '.seq4.bool')"
                  value: "<to_fill>"
            content: "jvm.eval(jvm.get('article_title_' + str(jvm.get('idx')) + '.seq3.str'))"

        - seq: 5
          type: If
          inside_loop: true
          objective: "If the article is relevant to AI, prepare to post it to Slack"
          rule_num: 5
          args:
            condition: "jvm.eval(jvm.get('is_relevant_' + str(jvm.get('idx')) + '.seq4.bool'))"
            then:
              - seq: 6
                type: TextCompletion
                inside_loop: true
                objective: "Prepare the message to be posted to Slack"
                rule_num: 3
                args:
                  command: "Generate the message to be posted to Slack"
                  output_fmt:
                    kvs:
                      - key: "jvm.eval('slack_message_' + str(jvm.get('idx')) + '.seq6.str')"
                        value: "<to_fill>"
                  content: "Here is an interesting AI-related article: jvm.eval(jvm.get('article_title_' + str(jvm.get('idx')) + '.seq3.str'))"
            else: []

end_seq: 6

overall_outcome: "The titles of the top 5 articles on Hacker News have been fetched and decisions have been made on whether to post them to a Slack channel. The messages prepared to be posted to Slack can be retrieved with keys like 'slack_message_<idx>.seq6.str'"
```
"""
}