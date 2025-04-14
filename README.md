# Kaliagent
Based on the sources, specifically the section titled "**Sales Team Automation Agent with Dify AI**", you can build a Dify AI workflow (which can also be considered a chatflow in this context of creating an agent) by following these steps for the initial email integration and text parsing stage:

*   **Step 1: Initiate the Workflow and Add the First Node: HTTP Request (Retrieve Email List)**.
    *   In Dify AI, you would start by creating a new workflow.
    *   The first node you need to add is an **"HTTP Request" node**. This node will be used to interact with the Gmail API to retrieve a list of emails.

*   **Step 2: Configure the HTTP Request Node for Gmail API Integration**. You need to set up the following configurations for this node:
    *   Set the **Method** to **GET**.
    *   Enter the Gmail API **URL** for listing messages: `https://www.googleapis.com/gmail/v1/users/me/messages`.
    *   Configure the **Headers**:
        *   Add a header with **Key**: `Authorization` and **Value**: `Bearer {{env.GMAIL_ACCESS_TOKEN}}`. This requires you to have a Gmail access token, likely stored as an environment variable in Dify AI. Obtaining this token involves the **Gmail API Integration** requirements outlined in the sources, such as creating a Google Cloud Project, enabling the Gmail API, obtaining **OAuth 2.0 credentials**, and generating the access token.
        *   Add another header with **Key**: `Content-Type` and **Value**: `application/json`.
    *   Define the **Params (Query Parameters)** to filter the emails:
        *   Add a parameter with **Key**: `q` and **Value**: `"PO" "Purchase Order"` to search for emails containing these keywords.
        *   Add a parameter with **Key**: `maxResults` and set the **Value** to the desired number of emails to retrieve (e.g., `10`).
    *   Set the **Body Type** to **None**.
    *   Name an **Output Variable** for this node, for example, `email_list`, to store the retrieved emails.

*   **Step 3: Add a "Parameter Extractor" Node**.
    *   Once you have the list of emails, the next step is to extract specific information from their content. Add a **"Parameter Extractor" node** to your workflow.
    *   Connect the output of the "HTTP Request" node (`email_list`) to the input of the "Parameter Extractor" node.

*   **Step 4: Configure the "Parameter Extractor" Node**. You need to define what information you want to extract and how:
    *   Set the **Output variable** to `HTTP request/Body`.
    *   Define **Extract Parameters** by providing a **Name** for each piece of information and a **Description/Prompt** that guides the AI in extracting that information. For example:
        *   **Parameter 1**: **Name**: `order_id`, **Description/Prompt**: `"Extract the Order ID or PO number from the email."`.
        *   **Parameter 2**: **Name**: `items_quantities`, **Description/Prompt**: `"List the items mentioned in the email along with their quantities."`.
        *   **Parameter 3**: **Name**: `customer_details`, **Description/Prompt**: `"Identify the customer name, email, or company from the email."`.
        *   **Parameter 4**: **Name**: `delivery_requirements`, **Description/Prompt**: `"Extract any delivery instructions or dates mentioned in the email."`.
    *   The **Instruction** for this node is to analyze the email content, potentially decode it if it's base64-encoded, and extract the specified parameters in a structured format.

After these steps, you should have the initial part of your Dify AI workflow set up to integrate with Gmail and extract data from purchase order emails. You can then test this by running the workflow with a connected Gmail account and reviewing the output of the "Parameter Extractor" node to see if it correctly identifies and extracts the desired information.
