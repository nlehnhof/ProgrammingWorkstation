# Documentation Preferences
#### Description
This document describes the preferences, context, and rules for writing documentation.

## Architecture
When directed to build documentation in a directory, build a documentation folder. All documentation files go here for that level of the directory. Within the folder:
 - [ ] READme.md file : a summary and explanation for the documentation folder.
 - [ ] WORKFLOW.md file : charts the workflow / higher-level interaction within the code.
 - [ ] CODE_EXPLAIN.md file: summarizes and explains the purpose for each page in the directory and sub-directories.
 - [ ] INSTRUCTIONS.md file: Explains how to use the code or how an operator would use the product
 - [ ] (Optional) THEORY.md file : explains the how and why with the code, but not the actual explanation of the code.

## File Rules
Describes the goal, context, and rules for each file in the documentation folder.
### READme.md
Goal: Write a short, concise description and table of contents for the documentation folder.
Context: This should be the first stop for anyone trying to understand the repository. By looking at READme.md, the user should grasp what each documentation file presents and how they interact together. They should know where to go to answer questions.
Rules:
Follow the format below for each file.
FILE NAME : Two-sentence description of contents.
    List of Key words in file.
    List questions (max 5) the file answers.
Include an overview summary at the top of the file. Similar to an abstract.
Update when the documentation folder updates.
Header should include version number, current branch, date-time of last commit, commit label.

### WORKFLOW.md
Goal: Show the workflow / higher-up interaction between code files. Should explain how all the files work together.
Context: This file helps the reader get a firm grasp of how files interact, focusing on how the navigation between files works, including "__init__" files and communications. It is more detailed than a summary, but doesn't dive into the code like CODE_EXPLAIN.md.
Rules: 
- Use code excerpts if it will make it clearer. 
- Cite lines and files and functions. 
- Don't change any code. 
- Read code only. 
- Update after 'git commit -m' commands
- When updated, add a "Recent Changes" section at the top that lists how the file logic and workflow changed with links to the pertinent sections in workflow.md for more information.
- Header should have date-time of last commit and commit label.

### CODE_EXPLAIN.md
Goal: A comprehensive explanation of code logic and functions at a function level.
Context: This file is the largest file and walks the user through each file and function, explaining what each thing does.
Rules:
 - Updates on 'git commit -m' commands
 - New changes section that lists the most recent updates and the why behind them.
 - Ask for complexity assignment (simple, medium, complex, expert-level)
 - Error on the side of simple
 - Short entries of less than two paragraphs
 - Cite files, lines, functions

### INSTRUCTIONS.md
Goal: Give the user instructions on how to use the application.
Context: The file gives the user a step-by-step on how to set up and run the repository / functions and files.
Rules: 
 - Starts with set-up instructions.
 - Walks the user through a small tutorial example / usage case.
 - Warnings
 - Future actions to take: bugs to fix, things to make it more efficient, suggestions for improvements.
 - FAQs section
 - Updates on 'git commit -m' commands.
 - Version and date-time in header.

### THEORY.md
Goal: Extracts the purpose of the repository and explains the theory behind it.
Context: If the repository is similar to a research repository or involves physics and mathematical concepts/theories, explain them. This document should extract the main principles and theories behind the code, giving the reader an understanding of why certain choices were made.
Rules: 
 - Ask before creating. 
 - Do not get into the weeds of the code. 
 - Stay focused on why certain actions were taken and explain the concept behind it (ex. explain what a Krylov Sovler is or the Kutta condition if the code follows that principle/theory).

## Preferences
This section compiles and records the preferences and customs of the user. This includes style, format, and expectations. 
As the DOCS.md file is used, ask the user three questions on format and style and record those answers here along with preferences learned from the directory. 