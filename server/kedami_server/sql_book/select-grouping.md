# SELECT: Grouping

In this chapter we will leave the level of individual rows and describe statements that refer to **groups of rows**. In the context of SQL such 'row-groups' (or sets of rows) are built by the GROUP BY clause and further processed by the HAVING clause.

## Constitute Groups

First we must establish criteria for filtering rows by groups. To do so we use the content of one or more columns of the involved table(s). If the values are identical, the rows belong to the same group. Consider the *lastname* in table *person*. In our small example we can insinuate that persons with same lastname form a family. So to see information about families we should use this column as the grouping criterion. This grouping allows us to ask questions concerning whole families, such as 'Which families are there?', 'How many families exists?', 'How many persons are in each family?'. All of these are questions about the whole group (which means the family), not about single rows (which means the person).

In the SQL syntax, the criterion is specified after the keyword GROUP BY and consists of one or more column names.

```sql
SELECT ...             -- as usual
FROM   ...             -- as usual (optionally plus JOINs)
GROUP BY <column-name>  -- optionally more column names
...                    -- optionally other elements of SELECT command
;
```

Our concrete example about families looks like this:

```sql
SELECT lastname
FROM   person
GROUP BY lastname;
```

The query retrieves seven 'family names' out of the ten rows. There are several persons with lastname 'Goldstein' or 'de Winter'.

We can retrieve the same seven 'family names' by applying the keyword DISTINCT in a SELECT without GROUP BY.

```sql
SELECT DISTINCT lastname
FROM   person;
-- no GROUP BY clause
```

What makes the difference? The DISTINCT keyword is limited to remove duplicate values. It can not initiate computations on other rows and columns of the result set. In contrast, the GROUP BY additionally arranges the intermediate received rows as several groups and offers the possibility to get information about each of these groups. It is even the case that within these groups **all** columns are available, not only the 'criterion'-column. To confirm this statement about 'all' columns, we use *weight*, which is not the 'criterion'-column.

```sql
SELECT lastname, avg(weight)  -- avg() is a function to compute the arithmetic mean of numerical values
FROM   person
GROUP BY lastname;
```

The result shows the seven family names - as seen before - plus the average weight of every family. The weight of individual persons is not shown. (In groups with precisely one person the average weight of the group is, of course, identical to the single person's weight.)

### Grouping over multiple columns

If necessary, we can define the grouping over more than one column. In this case, we can imagine the concatenation of the columns as the grouping rule.

```sql
-- Group over one column: place_of_birth leads to 6 resulting rows
SELECT place_of_birth, count(*)
FROM   person
GROUP BY place_of_birth;
-- Group over two columns: place_of_birth plus lastname leads to 8 resulting rows with Richland and SF shown twice
SELECT place_of_birth, lastname, count(*)
FROM   person
GROUP BY place_of_birth, lastname;
```

## Inspect Groups

After we have defined groups with the GROUP BY keyword, we can select more information about each of them, e.g.: how many persons (rows) exist within each family (group of rows)?

```sql
SELECT lastname, count(*)  -- count() is a function which counts values or rows
FROM   person
GROUP BY lastname;
```

We see that in our small example database there is one family with three members, another with two members and all others consist of exactly 1 member.

What is going on behind the scene during the execution of the command?
# All ten rows of table *person* are retrieved (in the above command, there is no WHERE clause).
# The rows are arranged into seven groups according to the value of column *lastname*.
# Every group with all of its rows is passed to the SELECT clause.
# The SELECT builds one resulting row for every received group (in 'real world' databases each of the groups may contain thousands of rows).

In step 4 **exactly one** resulting row is generated per group. Because the SELECT creates only one resulting row per group, it is not possible to show values of such columns which may differ from row to row, e.g., the firstname. The SELECT can only show such values of which it is ensured that they are identical within all rows of the group: the 'criterion'-column.

```sql
-- It is not possible to show the 'firstname' of a group! 'firstname' is an attribute of single person.
-- Within a group 'firstname' varies from row to row.
-- The DBMS should recognize this problem and should issue an error message.
SELECT lastname, firstname
FROM   person
GROUP BY lastname;
-- A hint to users of MySQL:
-- To receive correct results (the error message) you must deactivate a special performance feature by issuing the command
-- set sql_mode = 'ONLY_FULL_GROUP_BY'; or set it in the workbench or in the ini-file.
```

Nevertheless, we can get information about the non-criterion-columns. But this information is more generalized. The DBMS offers a special group of functions which build one value out of a set of rows. Consider the avg() function, which computes the arithmetic mean of numerical values. This function receives a column name and operates on a set of rows. If our command in question contains a GROUP BY clause, the avg() function does compute one value per group - not one value per all rows as usual. So it is possible to show the result of such functions together with the values of the 'criterion'-column.

Here is an - incomplete - list of such functions: count(), max(), min(), sum(), avg(). Not all functions are of that kind, e.g. the function concat(), which concatenates two strings, operates on single rows and creates one value per row.

```sql
-- compute avg() by your own formula
SELECT lastname, sum(weight) / count(weight) as "Mean weight 1", avg(weight) as "Mean weight 2"
FROM   person
GROUP BY lastname;
```

## Focus on Desired Groups

You know the WHERE clause. It defines which rows of a table will be part of the result set. The HAVING clause has the same meaning at the group-level. It determines which groups will be part of the result set.

```sql
-- The HAVING complements the GROUP BY
SELECT ...
FROM   ...
GROUP BY <columnname>
HAVING <having clause>; -- specify a criterion which can be applied to groups
```

We retrieve exclusively families with more than 1 members:

```sql
SELECT lastname
FROM   person
GROUP BY lastname    -- grouping over lastname
HAVING count(*) > 1; -- more than one person within the group
```

All families with one member are no longer part of the result.

In a second  example we focus on such groups which satisfies a criterion on column *firstname*. Consider that *firstname* is not the grouping-column.

```sql
-- Groups containing a person whose firstname has more than 4 characters: 5 resulting rows
SELECT lastname
FROM   person
GROUP BY lastname
HAVING max(length(firstname)) > 4; -- max() returns ONE value (the highest one) for all rows of each 'lastname'-group
```

The result shows the five families Baker, de Winter, Goldstein, Rich, and Stefanos (but not the row(s) with the long *firstname*).

Please note that this result is very different from the similar question to persons whose firstname has more than four characters:

```sql
-- Persons whose firstname has more than four characters: six resulting rows!!
SELECT lastname, firstname
FROM   person
WHERE  length(firstname) > 4;
-- no GROUP BY and no HAVING. The WHERE isn't an equivalent replacement for the HAVING!!
```

Where is the additional row coming from? In the family de Winter, there are two persons with a firstname longer than four characters: James and Victor. Because in the command without GROUP BY we select for persons and not for families, both rows are displayed individually.

In summary, we can say that the HAVING clause decides which groups are part of the result set and which are not.

## The Overall Picture

The GROUP BY and HAVING clauses are part of the SELECT command, and we can combine them with any other clauses of the SELECT as desired. Only the order of the clauses is obligatory.

```sql
-- This is the obligatory order of clauses
SELECT ...
FROM   ...
WHERE  ...
GROUP BY ...
HAVING   ...
ORDER BY ...
;
```

As mentioned, the WHERE clause works on the row-level, whereas the HAVING clause works on the group-level. First, the WHERE is evaluated, next the GROUP BY, next the HAVING, next the ORDER BY, and at the end the SELECT. Every step is based on the results of the previous one.

Finally we offer two additional examples:

```sql
-- Are there persons born on the same day?
SELECT date_of_birth  -- In a later chapter, you will learn how to select the name of these persons.
FROM   person
GROUP BY date_of_birth
HAVING count(date_of_birth) > 1 -- more than one on the same day?
ORDER BY date_of_birth;

-- Families with long first- and lastname. Comment out some lines to see differences to the original query.
SELECT lastname, count(*) as cnt 
FROM   person
WHERE  length(firstname) > 4  
GROUP BY lastname
HAVING length(lastname) > 4
ORDER BY cnt desc, lastname
;
```

## Exercises

**Exercise:** Are there persons born on the same day in the same city? Hint: group over both criteria

**Solution:**

```sql
SELECT date_of_birth, place_of_birth
FROM   person
GROUP BY date_of_birth, place_of_birth
HAVING   count(*) > 1;
```

**Exercise:** Categorise persons according to the formula: 'round (weight / 10)': 10 to 19 kg --> 1, 20 to 29 kg --> 2, ...

How much persons exist in each category?

**Solution:**

```sql
SELECT round (weight / 10), count(*)
FROM   person
GROUP BY round (weight / 10)
-- ORDER BY round (weight / 10)  -- order by category
ORDER BY count(*)                -- order by frequency
;
```

**Exercise:** Which contact type is used in which frequency in table contact?

**Solution:**

```sql
SELECT contact_type, count(*)
FROM   contact
GROUP BY contact_type
-- ORDER BY contact_type  -- order by contact_type
ORDER BY count(*)         -- order by frequency
;
```

**Exercise:** Restrict previous result to contact types which occurs more than once.

**Solution:**

```sql
SELECT contact_type, count(*)
FROM   contact
GROUP BY contact_type
HAVING   count(*) > 1
-- order by contact_type  -- order by contact_type
ORDER BY count(*)         -- order by frequency
;
```

**Exercise:** Are there persons performing more than 2 hobbies? Hint: check table person_hobby.

**Solution:**

```sql
SELECT person_id, count(*)
FROM   person_hobby
GROUP BY person_id
HAVING   count(*) > 2
;
```

**Exercise:** Are there persons performing only one hobby?

**Solution:**

```sql
SELECT person_id, count(*)
FROM   person_hobby
GROUP BY person_id
HAVING   count(*) = 1
;
```

**Exercise:** Are there persons performing no hobby?

**Solution:**

There are persons, who do not perform a hobby. But the nearby formulation 'count(*) = 0'
will not lead to the expected result because for such persons there are no rows
in table person_hobby, so the DBMS cannot create any group and hence cannot display anything.

Looking for something that does NOT exist is often more difficult than looking for the
existence of something. In such cases, you usually have to use one of: NOT EXISTS, NOT IN,
a combination of OUTER JOIN and IS NULL, a combination of OUTER JOIN and MINUS together
with INNER JOIN.
