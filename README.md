# Tax Calculator

A Python command-line application that helps Irish workers proportionally allocate annual income and tax credits across multiple jobs based on hours worked and hourly pay. Designed to support accurate Revenue profile updates for multi-employment scenarios.

## Features

- Accepts total annual income and tax credits
- Collects job details (company name, weekly hours, hourly rate)
- Estimates annual income per job
- Calculates proportional income distribution
- Allocates tax credits based on workload share
- Outputs a clear terminal summary

## Example

Scenario:

- Job A: 20 hours/week at €15/hour  
- Job B: 30 hours/week at €12/hour  
- Annual income: €30,000  
- Tax credits: €3,300  

The program calculates the fair distribution of income and tax credits across both employments.

## Requirements

- Python 3.x

## Run

```bash
python tax_split_calculator.py
