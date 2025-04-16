**Objective:** Identify the top 3 most critical problems from the provided UI analysis JSON.

**Input:**
The following is a JSON object containing a detailed analysis of a user interface. Focus on the `problemAreas` section.

```json
{analysis_json}
```

**Instructions:**

1.  Review the `problemAreas` list.
2.  Identify the top 3 problems based *only* on the `severity` score (higher is more critical).
3.  For each problem, extract its `description`.

**Output Format:**
Provide the response as a simple JSON list containing the descriptions of the top 3 problems.

**Example Output:**

```json
[
  "Description of the most critical problem...",
  "Description of the second most critical problem...",
  "Description of the third most critical problem..."
]
``` 

**Input:**
The following is a JSON object containing a detailed analysis of a user interface. Focus on the `problemAreas` section.

```json
{analysis_json}
```

**Instructions:**

1.  Review the `problemAreas` list.
2.  Identify the top 3 problems based *only* on the `severity` score (higher is more critical).
3.  For each problem, extract its `description`.

**Output Format:**
Provide the response as a simple JSON list containing the descriptions of the top 3 problems.

**Example Output:**

```json
[
  "Description of the most critical problem...",
  "Description of the second most critical problem...",
  "Description of the third most critical problem..."
]
``` 
 