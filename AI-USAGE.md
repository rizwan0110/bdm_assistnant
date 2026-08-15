# AI Usage

To complete this assignment within the given timeframe, I used AI to speed up the process. AI was used as a companion rather than the sole worker. I mainly used it for brainstorming, coding, debugging, and refining the writing.

## Tools Used

- **ChatGPT** — understanding the business problem, planning the MVP, reasoning about the data, debugging, testing, and documentation.
- **Codex** — coding support.

## How I Used AI

I used AI for tasks such as:

- Breaking the business problem into a small MVP
- Creating the development plan
- Designing the outlet priority logic
- Building the Streamlit BDM and Manager views
- Debugging issues
- Preparing end-to-end tests and documentation

### Example Instruction

One of my main instructions at the start was:

> "Help me break this assignment into small tasks. We will work on one task at a time. First explain what we are trying to achieve, then implement it, and test the result before moving to the next task."

This helped me work through the assignment step by step instead of generating the complete solution at once.

## One Place AI Was Wrong

During implementation, an AI-assisted solution used Pandas `groupby().apply()` to calculate business-value tiers within each territory.

The code ran, but testing showed this warning:

```text
DeprecationWarning: DataFrameGroupBy.apply operated on the grouping columns.
```

I caught this by checking the terminal output while testing the application.

I changed the implementation to process each territory group explicitly and combine the results using `pd.concat()`.

This removed the warning.

## Verification

I did not treat AI-generated code as automatically correct.

I manually checked:

- Data cleaning and BDM assignments
- Billing and visit metrics
- Activity classifications
- Business-value tiers
- Priority scores and recommendation reasons
- Visit capture and CSV persistence
- BDM and Manager workflows
- Edge cases through end-to-end testing