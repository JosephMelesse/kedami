# SELECT: Fundamentals

The SELECT command retrieves data from one or more tables or views. It generally consists of the following language elements:

```sql
SELECT   <things_to_be_displayed>  -- the so called 'Projection' - mostly a list of columnnames
FROM     <tablename>               -- table or view names and their aliases
WHERE    <where_clause>            -- the so called 'Restriction' or 'search condition'
GROUP BY <group_by_clause>
HAVING   <having_clause>
ORDER BY <order_by_clause>
OFFSET   <offset_clause>
FETCH    <fetch_first_or_next_clause>;
```

With the exception of the first two elements all others are optional. The sequence of language elements is mandatory. At certain places within the command there may start new SELECT commands - in a recursive manner.

## Projection (specify resulting columns)

In the projection part of the SELECT command, you specify a list of columns, operations working on columns, functions, fixed values, or new SELECT commands.

```sql
-- C/Java style comments are possible within SQL commands
SELECT id,                          /* the name of a column   */
       concat(firstname, lastname), /* the concat() function  */
       weight + 5,                  /* the add operation      */
       'kg'                         /* a value                */
FROM   person;
```

The DBMS will retrieve ten rows, each of which consists of four columns.

We can mix the sequence of columns in any order or retrieve them several times.

```sql
SELECT id, lastname, lastname, 'weighs', weight, 'kg'
FROM   person;
```

The asterisk '*' is an abbreviation for the list of all columns.

```sql
SELECT * FROM person;
```

For numeric columns, we can apply the usual numeric operators +, -, * and /. There are also many predefined functions depending on the data type: power, sqrt, modulo, string functions, date functions.

### Uniqueness via keyword DISTINCT

It is possible to compact the result in the sense of unique values by using the keyword DISTINCT. In this case, all resulting **rows**, which would be identical, will be compressed to one **row**. In other words: duplicates are eliminated - just like in set theory.

```sql
-- retrieves ten rows
SELECT lastname
FROM   person;
-- retrieves only seven rows. Duplicate values are thrown away.
SELECT DISTINCT lastname
FROM   person;
-- Hint:
-- The keyword 'DISTINCT' refers to the entirety of the resulting rows, which you can imagine as
-- the concatenation of all columns. It follows directly behind the SELECT keyword.
-- The following query leads to ten rows, although three persons have the same lastname.
SELECT DISTINCT lastname, firstname
FROM   person;
-- again only seven rows
SELECT DISTINCT lastname, lastname
FROM   person;
```

### Aliases for Column names

Sometimes we want to give resulting columns more descriptive names. We can do so by choosing an alias within the projection. This alias is the new name within the result set. GUIs show the alias as the column label.

```sql
-- The keyword 'AS' is optional
SELECT lastname AS family_name, weight AS weight_in_kg
FROM   person;
```

### Functions

There are predefined functions for use in projections (and at some other positions). The most frequently used are:
* count(<columnname>|'*'): Counts the number of resulting rows.
* max(<columnname>): The highest value in <column> of the resultset. Also applicable on strings.
* min(<columnname>): The lowest value in <column> of the resultset. Also applicable on strings.
* sum(<columnname>): The sum of all values in a numeric column.
* avg(<columnname>): The average of a numeric column.
* concat(<columnname_1>, <columnname_2>): The concatenation of two columns. Alternatively the function may be expressed by the '||' operator: <columnname_1> || <columnname_2>
Standard SQL and every DBMS offers many more functions.

We must differentiate between those functions which return one value per row like concat() and those which return only one row per complete resultset like max(). The former one may be mixed in any combination with column names, as shown in the very first example of this page. With the later ones, there exists a problem: If we mix them with a regular column name, the DBMS recognises a contradiction in the query. On the one hand it should retrieve precisely one value (in one row), and on the other hand, it should retrieve a lot of values (in a lot of rows). The reaction of DBMS differs from vendor to vendor. Some throw an error message at runtime - in accordance with the SQL standard -, others deliver suspicious results.

```sql
-- works fine
SELECT lastname, concat(weight, ' kg')
FROM   person;
-- check the reaction of your DBMS. It should throw an error message.
SELECT lastname, avg(weight)
FROM   person;
```

```sql
-- a legal mixture of functions resulting in one row with 4 columns
SELECT min(weight), max(weight), avg(weight) as average_1, sum(weight) / count(*) as average_2
FROM   person;
```

### SELECT within SELECT

If we **really** want to see the result of a result-set-oriented-function in combination with columns of more than one row, we can start a very new SELECT on a location where - in simple cases - a column name occurs. This second SELECT is an absolutely independent command. Be careful: It will be executed for **every** resulting row of the first SELECT!

```sql
-- retrieves 10 rows; notice the additional parenthesis to delimit the two SELECTs from each other.
SELECT lastname, (SELECT avg(weight) FROM person)
FROM   person;
-- Compute the percentage of each persons weight in relation to the average weight of all persons
SELECT lastname,
       weight,
       weight * 100 / (SELECT avg(weight) FROM person) AS percentage_of_average
FROM   person;
```

## Table Names

The Keyword FROM is used to specify the table on which the command will work.  This table name can be used as an identifier. In the first simple examples prefixing column names with the table name identifier can be used but isn't required. In the later more complex command, the table name identifier is a needed feature.

```sql
SELECT person.firstname, person.lastname
FROM   person;
-- Define an alias for the table name (analog to column names). To retain overview we usually
-- abbreviate tables by the first character of their name.
SELECT p.firstname, p.lastname
FROM   person AS p;  -- Hint: not all systems accept keyword 'AS' with table aliases. Omit it in these cases!
-- The keyword 'AS' is optional again.
SELECT p.firstname, p.lastname
FROM   person p;
```

## Restriction (specify resulting rows)

In the WHERE clause, we specify some 'search conditions' which are among the named table(s) or view(s). The evaluation of this criteria is - mostly - one of the first things during the execution of a SELECT command. Before any row can be sorted or displayed, it must meet the conditions in the clause.

If we omit the clause, all rows of the table are retrieved. Else the number of rows will be reduced according to the specified criteria. If we specify 'weight < 70', for example, only those rows are retrieved where the weight column stores a value less than 70. The restrictions act on **rows** of **tables** by evaluating **column values** (sometimes they act on other things like the existence of rows, but for the moment we focus on basic principles). As a result, we can imagine that the evaluation of the 'where clause' produces a list of rows. This list of rows will be processed in further steps like sorting, grouping, or displaying certain columns (projection).

### Comparisons

We compare variables, constant values, and results of function calls with each other in the same way as we would do in different programming languages. The only difference is that we use column names instead of variables. The comparison operators must match the given data types they have to operate on. The result of the comparison is a boolean value. If it is 'true', the according row will be processed furthermore. Some examples:
* 'weight = 70' compares the column 'weight' with the constant value '70' whether the column is equal to the constant value.
* '70 = weight': same as before.
* 'firstname = lastname' compares two columns - each of the **same** row - for equality. Names like 'Frederic Frederic' evaluate to true.
* 'firstname < lastname' is a fair comparison of two columns according to the lexical order of strings.
* 'LENGTH(firstname) < 5' compares the result of a function call to the constant value '5'. The function LENGTH() operates on strings and returns a number.

### Boolean Logic

Often we want to specify more than a single search criterion, e.g., are there people born in San Francisco with lastname Baker? To do this, we specify every necessary comparison independent from the next one and join them together with the boolean operators AND respectively OR.

```sql
SELECT *
FROM   person
WHERE  place_of_birth = 'San Francisco'
AND    lastname = 'Baker';
```

The result of a comparison is a boolean. It may be toggled between 'true' and 'false' by the unary operator NOT.

```sql
SELECT  *
FROM    person
WHERE   place_of_birth = 'San Francisco'
AND NOT lastname = 'Baker'; -- all except 'Baker'
-- for clarification: The NOT in the previous example is a 'unary operation' on the result of the
--                    comparison. It's not an addition to the AND.  
SELECT  *
FROM    person
WHERE   place_of_birth = 'San Francisco'
AND (NOT (lastname = 'Baker'));   --  same as before, but explicit notated with parenthesis
```

The **precedence** of comparisons and boolean logic is as follows:
# all comparisons
# NOT operator
# AND operator
# OR operator

```sql
-- AND (born in SF and lastname Baker; 1 hit as an intermediate result) will be processed before
-- OR  (person Yorgos; 1 hit)
-- 1 + 1 ==> 2 rows
SELECT *
FROM   person
WHERE  place_of_birth = 'San Francisco' -- 4 hits SF
AND    lastname = 'Baker'               -- 1 hit Baker
OR     firstname = 'Yorgos'             -- 1 hit Yorgos
;

-- Same example with parentheses added to make the precedence explicit.
-- AND gets processed before OR.
-- results ==> same 2 rows as above
SELECT *
FROM   person
WHERE  (place_of_birth = 'San Francisco' -- 4 hits SF
AND    lastname = 'Baker')              -- 1 hit Baker
OR     firstname = 'Yorgos'             -- 1 hit Yorgos
;

-- AND (person Yorgos Baker; no hit as an intermediate result) will be processed before
-- OR  (born in SF; 4 hits)
-- 0 + 4 ==> 4 rows
SELECT *
FROM   person
WHERE  place_of_birth = 'San Francisco' -- 4 hits SF
OR     firstname = 'Yorgos'             -- 1 hit Yorgos
AND    lastname = 'Baker'               -- 1 hit Baker
;

-- Same example with parentheses added to make the precedence explicit.
-- AND gets processed before OR.
-- results ==> same 4 rows as above
SELECT *
FROM   person
WHERE  place_of_birth = 'San Francisco'  -- 4 hits SF
OR     (firstname = 'Yorgos'             -- 1 hit Yorgos
AND    lastname = 'Baker')               -- 1 hit Baker
;

-- We can modify the sequence of evaluations by specifying parentheses.
-- Same as the first example, adding parentheses, one row.
SELECT *
FROM   person
WHERE  place_of_birth = 'San Francisco' -- 4 hits SF
AND   (lastname = 'Baker'               -- 1 hit Baker
OR     firstname = 'Yorgos')            -- 1 hit Yorgos
;
```

**Two abbreviations**

Sometimes we shorten the syntax by using the BETWEEN keyword. It defines a lower and upper limit and is primarily used for numeric and date values, but also applicable to strings.

```sql
SELECT *
FROM   person
WHERE  weight >= 70
AND    weight <= 90;
-- An equivalent shorter and more expressive wording
SELECT *
FROM   person
WHERE  weight BETWEEN 70 AND 90; -- BETWEEN includes the two cutting edges
```

For the comparison of a column or function with several values, we can use the short IN expression.

```sql
SELECT *
FROM   person
WHERE  lastname = 'de Winter'
OR     lastname = 'Baker';
-- An equivalent shorter and more expressive wording
SELECT *
FROM   person
WHERE  lastname IN ('de Winter', 'Baker');
```

### FETCH: Pick and Choose certain Rows

Sometimes we are not interested in all resulting rows, e.g.: we may want to see only the first 3 or 10 rows. This can be achieved with the OFFSET and FETCH clauses. OFFSET specifies the number of rows to be skipped (counting from the beginning of the result set), and FETCH specifies the number of rows, after which the delivery of rows shall stop.

```sql
SELECT *
FROM   person
WHERE  place_of_birth = 'San Francisco'
ORDER BY firstname
FETCH FIRST 2 ROWS ONLY  -- only the first 2 rows
;

SELECT *
FROM   person
ORDER BY id              -- the WHERE clause (and the ORDER BY clause) are optional
OFFSET 5 ROWS
FETCH FIRST 2 ROWS ONLY  -- only the 6th and 7th row (according to the ORDER BY)
;
```

Please notice that the OFFSET and FETCH clauses are separate parts of the SELECT command. Some implementations handle this functionality as part of the WHERE clause or with different keywords (ROWNUM, START, SKIP, LIMIT).

The functionality of OFFSET and FETCH can be achieved likewise by window functions with their more general syntax.

## Grouping

We will offer the GROUP BY clause in combination with the HAVING clause in a later chapter.

## Sorting

The DBMS is free to deliver the resulting rows in an arbitrary order. Rows may be returned in the order of the Primary Key, in the chronological order they are stored into the database, in the order of a B-tree organized internal key, or even in random order. Concerning the sequence of delivered rows, the DBMS may do what it wants to do. Don't expect anything.

If we expect a particular order of rows, we must express our wishes explicitly. We can do this in the ORDER BY clause. There we specify a list of column names in combination with an option for ascending or descending sorting.

```sql
-- all persons in ascending (which is the default) order of their weight
SELECT *
FROM   person
ORDER BY weight;
-- all persons in descending order of their weight
SELECT *
FROM   person
ORDER BY weight desc;
```

In the above result, there are two rows with identical values in the column *weight*. As this situation leads to random results, we have the possibility to specify more columns. These following columns are processed only for those rows with identical values in all previous columns.

```sql
-- All persons in descending order of their weight. In ambiguous cases order the 
-- additional column place_of_birth ascending: Birmingham before San Francisco.
SELECT *
FROM   person
ORDER BY weight desc, place_of_birth;
```

In the ORDER BY clause, we can specify any column of the processed table. We are not limited to the ones which are returned by the projection.

```sql
-- same ordering as above
SELECT firstname, lastname
FROM   person
ORDER BY weight desc, place_of_birth;
```

## Combine the Language Elements

Only the first two elements of the SELECT command are mandatory: the part up to the first table (or view) name. All others are optional. If we also specify the optional ones, their predetermined sequence must be kept in mind. But they are combinable according to our needs.

```sql
-- We have seen on this page: SELECT / FROM / WHERE / ORDER BY
SELECT p.lastname,
       p.weight,
       p.weight * 100 / (SELECT avg(p2.weight) FROM person p2) AS percentage_of_average
FROM   person p
WHERE  p.weight BETWEEN 70 AND 90
ORDER BY p.weight desc, p.place_of_birth;
```

## Further Information

There is more information about the additional options for the SELECT command.
- Join Operation
- Grouping
- IS NULL Predicate
- Predefined Functions
- Set Operations
- Case Expression
- Like Predicate
- Subquery

## Exercises

**Exercise:** Show hobbyname and remark from the hobby table.

**Solution:**

```sql
SELECT hobbyname, remark
FROM   hobby;
```

**Exercise:** Show hobbyname and remark from the hobby table. Order the result by hobbyname.

**Solution:**

```sql
SELECT hobbyname, remark
FROM   hobby
ORDER BY hobbyname;
```

**Exercise:** Show hobbyname and remark from the hobby table. Choose 'Hobby' as first columnname and 'Short_Description_of_Hobby' as second columnname.

**Solution:**

```sql
SELECT hobbyname as Hobby, remark as Short_Description_of_Hobby
FROM   hobby;
-- columnname without underscore: Use quotes
SELECT hobbyname as "Hobby", remark as "Short Description of Hobby"
FROM   hobby;
```

**Exercise:** Show firstname and lastname of persons born in San Francisco.

**Solution:**

```sql
SELECT firstname, lastname
FROM   person
WHERE  place_of_birth = 'San Francisco';
```

**Exercise:** Show all information items of persons with lastname 'de Winter'.

**Solution:**

```sql
SELECT *
FROM   person
WHERE  lastname = 'de Winter';
```

**Exercise:** How many rows are stored in the contact table?

**Solution:**

```sql
SELECT count(*)
FROM   contact;
9
```

**Exercise:** How many E-Mails are stored in the contact table?

**Solution:**

```sql
SELECT count(*)
FROM   contact
WHERE  contact_type = 'email';
3
```

**Exercise:** What is the mean weight of persons born in San Francisco?

**Solution:**

```sql
SELECT avg(weight)
FROM   person
WHERE  place_of_birth = 'San Francisco';
71.25
```

**Exercise:** Find persons born after 1979-12-31, which weigh more than / less than 50 kg.

**Solution:**

```sql
SELECT *
FROM   person
WHERE  date_of_birth > DATE '1979-12-31'
AND    weight > 50;
--
SELECT *
FROM   person
WHERE  date_of_birth > DATE '1979-12-31'
AND    weight < 50;
```

**Exercise:** Find persons born in Birmingham, Mumbai, Shanghai or Athens in the order of their firstname.

**Solution:**

```sql
SELECT *
FROM   person
WHERE  place_of_birth = 'Birmingham'
OR     place_of_birth = 'Mumbai'
OR     place_of_birth = 'Shanghai'
OR     place_of_birth = 'Athens'
ORDER BY firstname;
-- equivalent:
SELECT *
FROM   person
WHERE  place_of_birth IN ('Birmingham', 'Mumbai', 'Shanghai', 'Athens')
ORDER BY firstname;
```

**Exercise:** Find persons born in Birmingham, Mumbai, Shanghai or Athens within the 21st century.

**Solution:**

```sql
SELECT *
FROM   person
WHERE  (   place_of_birth = 'Birmingham'
        OR place_of_birth = 'Mumbai' 
        OR place_of_birth = 'Shanghai'
        OR place_of_birth = 'Athens'
       )
AND    date_of_birth >= DATE '2000-01-01'
AND    date_of_birth <= DATE '2099-12-31';
-- equivalent:
SELECT *
FROM   person
WHERE  place_of_birth IN ('Birmingham', 'Mumbai', 'Shanghai', 'Athens')
AND    date_of_birth >= DATE '2000-01-01'
AND    date_of_birth <= DATE '2099-12-31';
```

**Exercise:** Find persons born between Dallas and Richland ('between' not in the sense of a geographic area but of the lexical order of citynames)

**Solution:**

```sql
-- strings have a lexical order. So we can use some operators known
-- from numeric data types.
SELECT *
FROM   person
WHERE  place_of_birth >= 'Dallas'
AND    place_of_birth <= 'Richland'
ORDER BY place_of_birth;
-- equivalent:
SELECT *
FROM   person
WHERE  place_of_birth BETWEEN 'Dallas' AND 'Richland'
ORDER BY place_of_birth;
```

**Exercise:** Which kind of contacts are stored in the contact table? (Only one row per value.)

**Solution:**

```sql
SELECT DISTINCT contact_type
FROM   contact;
fixed line
email
icq
mobile
```

**Exercise:** How many different kind of contacts are stored in the contact table? (Hint: Count the rows of above query.)

**Solution:**

```sql
SELECT count(DISTINCT contact_type)
FROM   contact;
4
```

**Exercise:** Show contact_type, contact_value and a string of the form 'total number of contacts: <x>', where <x> is the quantity of all existing contacts.

**Solution:**

```sql
SELECT contact_type, contact_value,
       (SELECT concat('total number of contacts: ', count(*)) FROM contact)
FROM   contact;
-- Some systems need explicit type casting from numeric to string
SELECT contact_type, contact_value,
       (SELECT concat('total number of contacts: ', cast(count(*) as char)) FROM contact)
FROM   contact;
-- The '||' operator is some kind of 'syntactical sugar'. It's an abbreviation for the concat() function.
-- The operator is part of the SQL standard, but not implemented by all vendors.
SELECT contact_type, contact_value,
       (SELECT 'total number of contacts: ' || count(*) FROM contact)
FROM   contact;
```
