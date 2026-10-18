# SELECT: Predefined Functions

There are two groups of predefined functions:
***aggregate functions**. They work on a set of rows, which means they receive one value for each row of a set of rows and returns one value for the whole set. If they are called in the context of a GROUP BY clause, they are called once per group, else once for all rows.
* **scalar functions**. They work on single rows, which means they receive one value of a single row and returns one value for each of them.

## Aggregate functions

They work on a set of rows and return one single value like the number of rows, the highest or lowest value, the standard deviation, etc. The most important aggregate functions are:

| Signatur | Semantic |
| --- | --- |
| `COUNT(*)` | The number of rows |
| `COUNT(<column name>)` | The number of rows where <column name> contains a value (IS NOT NULL). The elimination of rows with the NULL special marker in the considered column applies to all aggregate functions. |
| `MIN(<column name>)` | Lowest value. In the case of strings according to the sequence of characters. |
| `MAX(<column name>)` | Highest value. In the case of strings according to the sequence of characters. |
| `SUM(<column name>)` | Sum of all values |
| `AVG(<column name>`) | Arithmetic mean |

As an example we retrieve the maximum weight of all persons:

```sql
SELECT MAX(weight)
FROM   person;
```

A Word of Caution

Aggregate functions result in one value for a set of rows. Therefore it is not possible to use them together with 'normal' columns in the projection (the part behind SELECT keyword). If we specify, for example,

```sql
SELECT lastname, SUM(weight)
FROM   person;
```

we try to instruct the DBMS to show a **lot of rows** containing the *lastname* simultaneously with **one** value. This is a contradiction and the system will throw an exception. We can use a lot of aggregate functions within one projection but we are not allowed to use them together with 'normal' columns.

```sql
-- Multiple aggregate functions. No 'normal' columns.
SELECT SUM(weight)/COUNT(weight) as average_1, AVG(weight) as average_2
FROM   person;
```

Grouping

If we use aggregate functions in the context of commands containing a GROUP BY, the aggregate functions are called once per group.

```sql
-- Not only one resulting row, but one resulting row per lastname together with the average weight of all rows with this lastname.
SELECT AVG(weight)
FROM   person
GROUP BY lastname;
```

In such cases the GROUP BY column(s) may be displayed as it is impossible that they change within the group.

```sql
-- The lastname may be shown as it is the GROUP BY criteria
SELECT lastname, AVG(weight)
FROM   person
GROUP BY lastname;
```

### The NULL special marker

If a row contains no value (it holds the NULL special marker) in the named column, the row is not part of the computation.

```sql
-- If ssn is NULL, this row will not count.
SELECT COUNT(ssn)
FROM   person;
```

### ALL vs. DISTINCT

The complete signatures of the functions are a little more detailed. We can prepend the column name with one of the two key words ALL or DISTINCT. If we specify ALL, which is the default, every value is part of the computation, else only those, which are distinct from each other.

```
function_name ([ALL|DISTINCT]<column name>)
COUNT (DISTINCT weight) -- as an example
```

### Hint

The standard defines some more aggregate functions to compute statistical measures. Also the keywords ANY, EVERY and SOME formally are defined as aggregate functions. We will discuss them on a separate page.

## Scalar functions

Scalar functions act on a 'per row basis'. They are called once per row and they return one value per call. Often they are grouped according to the data types they act on:

* String functions
SUBSTRING(<column name> FROM <pos> FOR <len>) returns a string starting at position <pos> (first character counts '1') in the length of <len>.
UPPER(<column name>) returns the uppercase equivalent of the column value.
LOWER(<column name>) returns the lowercase equivalent of the column value.
CHARACTER_LENGTH(<column name>) returns the length of the column value.
TRIM(<column name>) returns the column value without leading and trailing spaces.
TRIM(LEADING  FROM <column name>) returns the column value without leading spaces.
TRIM(TRAILING FROM <column name>) returns the column value without trailing spaces.

* Numeric functions
SQRT(<column name>) returns the square root of the column value.
ABS(<column name>) returns the absolute value of the column value.
MOD(<column name>, ) returns the remaining of column value divided by divisor.
others: FLOOR, CEIL, POWER, EXP, LN.

* Date, Time & Interval functions
EXTRACT(month FROM date_of_birth) returns the month of column date_of_birth.

* build-in functions. They do not have any input parameter.
CURRENT_DATE() returns the current date.
CURRENT_TIME() returns the current time.
There is another wikibook where those functions are shown in detail. The data type of the return value is not always identical to the type of the input, e.g. 'character_length()' receives a string and returns a number.

Here is an example with some scalar functions:

```sql
SELECT LOWER(firstname), UPPER(lastname), CONCAT('today is: ', CURRENT_DATE)
FROM   person;
```

## Exercises

**Exercise:** What is the hightest id used so far in the hobby table?

**Solution:**

```sql
SELECT max(id)
FROM   hobby;
```

**Exercise:** Which lastname will occur first in an ordered list?

**Solution:**

```sql
SELECT min(lastname)
FROM   person;
```

**Exercise:** Are there aggregate functions where it makes no difference to use the ALL or the DISTINCT key word?

**Solution:**

Yes. min(ALL <column name>) leads to the same result as min(DISTINCT <column name>) as

 it makes no difference whether the smallest value occurs one or more times. The same is true for max().

**Exercise:** Show persons with a short firstname (up to 4 characters).

**Solution:**

```sql
-- We can use functions as part of the WHERE clause.
SELECT *
FROM   person
WHERE  character_length(firstname) <= 4; -- Hint: Some implementations use a different function name: length() or len().
```

**Exercise:** Show firstname, lastname and the number of characters for the concatenated string. Find two different solutions. You may use the character_length() function to compute the length of strings and the concat() function to concatenate strings.

**Solution:**

```sql
-- Addition of the computed length. Hint: Some implementations use a different function name: length() or len().
SELECT firstname, lastname, character_length(firstname) + character_length(lastname)
FROM   person;
-- length of the concatenated string
SELECT firstname, lastname, character_length(concat (firstname, lastname))
FROM   person;
-- show both solutions together
SELECT firstname, lastname,
       character_length(firstname) + character_length(lastname) as L1,
       character_length(concat (firstname, lastname)) as L2
FROM   person;
```
