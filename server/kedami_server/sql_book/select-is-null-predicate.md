# SELECT: IS NULL Predicate

When creating new rows, it may occur that we don't know the value of one or more columns.

Let's assume that we want to store information about banking accounts, and for one of those accounts we don't know the balance. What can we do? There are several possibilities:
* **Reject** the whole row with all other information like account number, dispositional credit, interest rate, ... . Not very attractive.
* Store a **default value** instead of the value we currently don't know. But there are cases where it is impossible to define a default value because every value is possible, e.g., a bank account of '0' or '-1' is not unusual.
* Store a **flag** that signals that no value is stored. This approach is similar to the *Not-a-Number* technique.
Relational DBMS uses the last mentioned technique, and the sense of the flag is 'there is no value stored'. Sometimes people say 'The **NULL** value is stored' or 'The **NULL** special marker is stored'.

## Extension of Boolean Logic

Assume there is a table for banking accounts, and some of its rows hold the NULL special marker in the column *balance*. Do those rows fulfill at least one of the two WHERE conditions 'balance >= 0' or 'balance <= 0'? No. It is not possible to decide whether these conditions are true or false! Honestly, we must admit that we don't know an answer in our usual true/false logic because we don't know a value for *balance*. We are forced to extend the range of boolean values with a third one, which we call **unknown**. The two conditions above evaluate neither true nor false; both evaluate to 'unknown' for rows where *balance* holds the NULL special marker.

In a later stage, we need definitions for the boolean operators NOT, AND, OR, and EQUAL when true/false interact with unknown. You find the definitions here.

## Retrieve the NULL Special Marker

Within every SELECT command, such rows become part of the resulting rows, in which the WHERE condition evaluates to true. If it evaluates to false or unknown, the row will be rejected. As **all** WHERE conditions like the above 'balance >= 0' - and also their negation - evaluates to unknown for missing *balance* values, there is preliminary no way to retrieve them.

To overcome this lack, SQL contains the particular phrase 'IS NULL'. The wording 'balance IS NULL' evaluates to true for precisely the rows with a missing value in *balance*.

```sql
SELECT ...
FROM   ...
WHERE  <columnname> IS NULL
...    
;
```

We must use exactly this wording. The use of any arithmetic operator like >, <=, !=, ... will not retrieve rows with the NULL special marker. The same holds true even for the condition '(balance = 0) OR NOT (balance = 0)', which is a tautology in conventional true/false logic. Besides this IS NULL predicate, there is no other way to retrieve the NULL special marker - without one simple but not helpful exception: if you omit the WHERE condition, all rows of the table are retrieved, with and without NULL special marker in any column.

That's all! Dealing with NULL special marker and the 3-value-logic might sound strange if you first met this topic. But as the IS NULL predicate always evaluates to true or false, everything works as usual afterward. We can use all other elements of the SELECT command (boolean logic, join, having, order by, ...) in the same way we have done so far.

## Some Examples

Our test database does not contain the NULL special marker. Nevertheless, we have met the situation during the explanation of OUTER joins. OUTER joins create resulting rows where some columns contain the NULL special marker. We must consider this possibility if we deal with the results of such subselects.

There are two other ways to generate the NULL special marker.
* INSERT or UPDATE command with the explicit notion of the NULL special marker. In this case, the SQL keyword **null** is used as a representative for the NULL special marker.
* INSERT command without using all columns. The omitted columns will get the NULL special marker - or a default, if one is defined.
To demonstrate this and to create some examples for the following exercises, we put one row into the *person* table with some columns left empty.

```sql
-- Insert a new row for testing purpose
INSERT INTO person (id, firstname, lastname)  VALUES (51, 'Half man', 'Uncomplete');
COMMIT;

-- Retrieve the row. As defined in CREATE TABLE statement the weight has a default value of integer 0.
-- Date_of_birth and place_of_birth contain the NULL special marker.
SELECT * FROM person WHERE  id = 51;

-- use the IS NULL predicate within WHERE clause. The result contains 1 row.
SELECT * FROM person WHERE ssn IS NULL;

-- weight has a value!! We expect to retrieve no rows when we use the IS NULL predicate.
SELECT * FROM person WHERE weight IS NULL;
-- or, to say it the other way round, the number of rows is 0
SELECT count(*) FROM person WHERE weight IS NULL;
-- but in the next statement the number of rows is 1
SELECT count(*) FROM person WHERE weight = 0;

-- Negate the IS NULL predicate
SELECT count(*) FROM person WHERE ssn IS NULL;     -- IS NULL
SELECT count(*) FROM person WHERE ssn IS NOT NULL; -- Negation of IS NULL

SELECT count(*)
FROM   person
WHERE  ssn IS NULL
OR     ssn IS NOT NULL; -- A tautology, which always retrieves ALL rows of a table
-- Same as above
SELECT count(*)
FROM   person
WHERE  ssn IS NULL
OR NOT ssn IS NULL; -- A tautology, which always retrieves ALL rows of a table
```

Next we show the use of the UPDATE command in combination with the key word NULL

```sql
--
-- Insert a new row for testing purpose with all columns filled with a useful value
INSERT INTO person (id, firstname, lastname,  date_of_birth,    place_of_birth, ssn,           weight)
VALUES             (52, 'Lyn',     'Mutable', DATE'1951-05-13', 'Anchorage',    '078-05-1152', 69);
COMMIT;
SELECT * FROM person WHERE id = 52;

-- Delete a single column value (not the complete row)
UPDATE person SET ssn = null WHERE id = 52;
COMMIT;
SELECT * FROM person WHERE id = 52;      -- one row
SELECT * FROM person WHERE ssn IS NULL;  -- two rows: 51 + 52
```

Restore the original state of the example database.

```sql
DELETE FROM person WHERE id > 50;
COMMIT;
```

## Coalesce() and Similar Functions

In the context of the NULL special marker it is often the case that we have to retrieve rows with no value (the NULL special marker) **or** a default value such as 0 or blank. In such cases, the WHERE condition looks something like this: "... WHERE (col IS NULL OR col = 0) ...". To keep source code simpler, the SQL standard defines a function **coalesce(<expression_1>, <expression_2>)**. If the first argument, which normally is the name of a column, is not NULL, the function evaluates to this argument - else to the second argument.

Example:

```sql
-- Retrieve rows without ssn or with ssn equal to blank.
SELECT *
FROM   person
WHERE  coalesce(ssn, ' ') = ' ';
-- equivalent:
-- WHERE (ssn IS NULL
-- OR     ssn = ' ');
```

The function name *coalesce* results from the fact that the function accepts an arbitrary number of parameters and recursively evaluates them. If parameter *n* results in a real value, it evaluates to this parameter, else the function calls itself without the n-th parameter. coalesce(expression_1, expression_2, expression_3) evaluates to expression_1, if expression_1 is not NULL, else to expression_2, if expression_2 is not NULL, else to expression_3.

The SQL standard defines another function **nullif(<expression_1>, <expression_2>)**. It evaluates to NULL, if the two expressions are equal - and it evaluates to the first expression, if they differ from each other.

Different vendors offers some more functions like **isnull()**, **ifnull()** or **nvl()** to support handling of NULL values. The meanings of these functions are vendor specific.

## Exercises

**Exercise:** Insert a new hobby 'Snowshoeing' without a remark.

**Solution:**

```sql
INSERT INTO hobby (id, hobbyname,     remark)
VALUES            (10, 'Snowshoeing', null);
COMMIT;
```

**Exercise:** Find a second solution for the above question without using the key word 'null'. (First delete row 10.)

**Solution:**

```sql
DELETE FROM hobby WHERE id = 10;
INSERT INTO hobby (id, hobbyname)
VALUES            (10, 'Snowshoeing');
COMMIT;
```

**Exercise:** Retrieve all hobbies without a remark.

**Solution:**

```sql
-- 1 row
SELECT * FROM hobby WHERE remark IS NULL;
```

**Exercise:** How many hobbies are exemplified with a remark?

**Solution:**

```sql
-- 9 rows
SELECT count(*) FROM hobby WHERE remark IS NOT NULL;
```

**Exercise:** Change row 10 of hobby so that hobbyname contains the string 'NULL' and remark contains 'Name of hobby not known'.

**Solution:**

```sql
-- Consider the two apostrophes surrounding the string 'NULL', which consists of the 4 characters N, U, L and L !!
UPDATE hobby SET hobbyname = 'NULL', remark = 'Name of hobby not known' WHERE id = 10;
COMMIT;
```

**Exercise:** a) Retrieve the row where hobbyname is 'NULL'.
b) Retrieve the row where remark is 'Name of hobby not known'.

**Solution:**

```sql
-- This may be a pitfall question. There is no relation to the IS NULL predicate
SELECT * FROM hobby WHERE hobbyname = 'NULL';
SELECT * FROM hobby WHERE remark = 'Name of hobby not known';
```

**Exercise:** How many hobbies have a hobby name?

**Solution:**

```sql
-- All 10 rows contains a hobby name, even the row with the hobbyname 'NULL'
SELECT count(*) FROM hobby WHERE hobbyname IS NOT NULL;
```
