# SELECT: Join Operation

Data should be stored in such a way that no redundant information exists in the database. For example, if our database includes groups of people who, in each case, all pursue the same hobby, then we would rather avoid repeatedly storing the same static details about a given hobby; namely in every record about one of the hobby's enthusiasts. Likewise, we would rather avoid repeatedly storing the same detailed information about an individual hobbyist, namely in every record about one of that person's hobbies. Instead, we create independent *person* and *hobby* tables and point from one to the other. This technique for grouping data in separate, redundancy-free tables is called database normalization. Such separation also tends to simplify the logic and enhance the flexibility of assembling precisely the items needed for a given purpose. This assembly is accomplished through the 'JOIN' operation.

## The Idea

In our example database, there are two tables: *person* and *contact*. The *contact* table contains the column *person_id*, which correlates with the Primary-Key column *id* of the *person* table. By evaluating the column values, we can join contacts and persons together.

*person* table P

| ID | LASTNAME | FIRSTNAME | ... |
| --- | --- | --- | --- |
| 1 | Goldstein | Larry | ... |
| 2 | Burton | Tom | ... |
| 3 | Hamilton | Lisa | ... |
| 4 | Goldstein | Kim | ... |
| ... | ... | ... | ... |
| ... | ... | ... | ... |

*contact* table C

| ID | PERSON_ID | CONTACT_TYPE | CONTACT_VALUE |
| --- | --- | --- | --- |
| 1 | 1 | fixed line | 555-0100 |
| 2 | 1 | email | larry.goldstein@acme.xx |
| 3 | 1 | email | lg@my_company.xx |
| 4 | 1 | icq | 12111 |
| 5 | 4 | fixed line | 5550101 |
| 6 | 4 | mobile | 10123444444 |
| ... | ... | ... | ... |
| ... | ... | ... | ... |

Joined (virtual) table, created out of *person* and *contact*

| P.ID | P.LASTNAME | P.FIRSTNAME | ... | C.ID | C.PERSON_ID | C.CONTACT_TYPE | C.CONTACT_VALUE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Goldstein | Larry | ... | 1 | 1 | fixed line | 555-0100 |
| 1 | Goldstein | Larry | ... | 2 | 1 | email | larry.goldstein@acme.xx |
| 1 | Goldstein | Larry | ... | 3 | 1 | email | lg@my_company.xx |
| 1 | Goldstein | Larry | ... | 4 | 1 | icq | 12111 |
| 2 | Burton | Tom | ... | ? | ? | ? | ? |
| 3 | Hamilton | Lisa | ... | ? | ? | ? | ? |
| 4 | Goldstein | Kim | ... | 5 | 4 | fixed line | 5550101 |
| 4 | Goldstein | Kim | ... | 6 | 4 | mobile | 10123444444 |
| ... | ... | ... | ... | ... | ... | ... | ... |

So, Larry Goldstein, that exists only once in the stored *person* table, is now listed four times in the joined, virtual table – each time, in combination with one of his four contact items. The same applies to Kim Goldstein and his two contact items.

But what is going on with Tom Burton and Lisa Hamilton, whose contact information is not available? We may have some trouble attempting to join their *person* data with their non-existent *contact* information. For the moment, we have flagged the situation with question marks. A detailed explanation of how to transform the problem into a solution appears later on this page.

## The Basic Syntax

Obviously it's necessary to specify two things with the JOIN operation
* the names of the relevant tables
* the names of the relevant columns

The basic syntax extends the SELECT command with these two elements

```sql
SELECT <things_to_be_displayed>       -- as usual
FROM   <tablename_1> <table_1_alias>  -- a table alias
JOIN   <tablename_2> <table_2_alias> ON <join condition> -- the join criterion
...    -- optionally all the other elements of SELECT command
;
```

Let's make a first attempt.

```sql
SELECT *
FROM   person p
JOIN   contact c ON p.id = c.person_id;
```

One of the table names is referenced after the FROM keyword (as previously), and the other one after the new keyword, JOIN, which (no surprise here) instructs the DBMS to perform a join operation. Next, the ON keyword introduces the column names together with a comparison operator (or a general condition, as you will see later). The column names are prefixed with the respective aliases of the table names, *p* and *c*. This is necessary because columns with identical names (like *id*) may exist in multiple tables.

When the DBMS executes the command, it delivers 'something' that contains all the columns from both tables, including the two *id* columns from their respective (*person* and *contact*) tables.  The result contains nine rows, one per **existing** combination of person and contact; viz., due to the 'ON' expression, person records without any corresponding contact records will not appear in the result.

The delivered 'something' looks like a new table; in fact, it has the same structure, behavior, and data as a table. If it is created from a view or as the result of a subselection, we can even perform new SELECTs on it. But there is an important difference between this and a table: Its assembled data is **not stored** in the DBMS as such; rather, the data is **computed** at run time from the values of real tables, and only held in temporary memory while the DBMS is running your program.

This key feature – assembling complex information from simple tables – is made possible by means of the two simple keywords, JOIN and ON. As you will see also, the syntax can be extended to build very complex queries, such that you can add many additional refinements to the specification of your join criteria.

It can sometimes be confusing when results don't match your intentions. If this happens, try to simplify your query, as shown here. Confusion often results from the fact that the JOIN syntax itself may become quite complicated. Moreover, joining can be combined with all of the other syntactic elements of the SELECT command, which also may lead to a lack of clarity.

The combination of the join syntax with other language elements is shown in the following examples.

```sql
--
-- show only important columns
SELECT p.firstname, p.lastname, c.contact_type as "Kind of Contact", c.contact_value as "Call Number"
FROM   person p
JOIN   contact c ON p.id = c.person_id;

-- show only desired rows
SELECT p.firstname, p.lastname, c.contact_type as "Kind of Contact", c.contact_value as "Call Number"
FROM   person p
JOIN   contact c ON p.id = c.person_id
WHERE  c.contact_type IN ('fixed line', 'mobile');

-- apply any sort order
SELECT p.firstname, p.lastname, c.contact_type as "Kind of Contact", c.contact_value as "Call Number"
FROM   person p
JOIN   contact c ON p.id = c.person_id
WHERE  c.contact_type IN ('fixed line', 'mobile')
ORDER BY p.lastname, p.firstname, c.contact_type DESC;

-- use functions: min() / max() / count()
SELECT count(*)
FROM   person p
JOIN   contact c ON p.id = c.person_id
WHERE  c.contact_type IN ('fixed line', 'mobile');

-- JOIN a table with itself. Example: Search different persons with the same lastname
SELECT p1.id, p1.firstname, p1.lastname, p2.id, p2.firstname, p2.lastname
FROM   person p1
JOIN   person p2 ON p1.lastname = p2.lastname -- for the second incarnation of person we must use a different alias
WHERE  p1.id != p2.id
-- sorting of p2.lastname is not necessary as it is identical to the already sorted p1.lastname
ORDER BY p1.lastname, p1.firstname, p2.firstname;

-- JOIN more than two tables. Example: contact information of different persons with same lastname
SELECT p1.id, p1.firstname, p1.lastname, p2.id, p2.firstname, p2.lastname, c.contact_type, c.contact_value
FROM   person p1
JOIN   person p2 ON p1.lastname = p2.lastname
JOIN   contact c ON p2.id = c.person_id       -- contact info from person2. p1.id would lead to person1
WHERE  p1.id != p2.id
ORDER BY p1.lastname, p1.firstname, p2.lastname;
```

## Four Join Types

Earlier on this page, we saw an example of a join result wherein some rows contained person names, but no contact information – instead showing a question mark in that latter column. If the basic syntax of the JOIN operation had been used, those (question-mark) rows would have been filtered out. That (basic syntax with exclusive result) is known as an INNER join. There are also three different kinds of OUTER joins. The results of an OUTER join will contain not only all the full-data rows that an INNER join's results would, but also partial-data rows, i.e., those where no data was found in one or both of the two stored tables; thus, they're called LEFT OUTER, RIGHT OUTER and FULL OUTER joins.

So we can widen the basic JOIN syntax to the four options:
* [INNER] JOIN
* LEFT  [OUTER] JOIN
* RIGHT [OUTER] JOIN
* FULL  [OUTER] JOIN
Keywords surrounded by [ ] are optional. The parser infers OUTER from LEFT, RIGHT or FULL, and a plain (i.e., basic-syntax) JOIN defaults to INNER.

### Inner Join

The inner join is probably the most commonly used of the four types. As we have seen, it results in precisely those rows that exactly match the criterion following the ON. Below is an example showing how to create a list of persons and their contacts.

```sql
-- A list of persons and their contacts
SELECT p.firstname, p.lastname, c.contact_type, c.contact_value
FROM   person p
JOIN   contact c ON p.id = c.person_id  -- identical meaning: INNER JOIN ...
ORDER BY p.lastname, p.firstname, c.contact_type DESC, c.contact_value;
```

What is most significant is that records for persons without any contact information are **not** part of the result.

### Left (outer) Join

Sometimes we need a little more; for example, we might want a list of all person records, to include any contact-information records that may also be available for that person. Note how this differs from the example above: this time, the results will contain *all* person records, even those for persons who have **no** contact-information record(s).

```sql
-- A list of ALL persons plus their contacts
SELECT    p.firstname, p.lastname, c.contact_type, c.contact_value
FROM      person p
LEFT JOIN contact c ON p.id = c.person_id  -- identical meaning: LEFT OUTER JOIN ...
ORDER BY  p.lastname, p.firstname, c.contact_type DESC, c.contact_value;
```

In those cases where the contact information is unavailable, the DBMS will supplant it with the 'null value' or with the 'null special marker' (not to be confused with the *string* (-type) 'null value' or 'null' nor with binary 0.  Nonetheless, implementation details aren't important here. The null special marker will be discussed in a later chapter).

In summary, the left (outer) join is an inner join, plus one row for each left-side match without a counterpart on the right side.

Consider the word 'left'. It refers to the left side of the formula, "FROM <table_1> LEFT JOIN <table_2>", or more specifically, the table denoted on the left side (here: *table_1*); indicating that every row of that table will be represented at least once in the result, whether a corresponding record is found in the right-side table (here: *table_2*) or not.

Another example:

```sql
SELECT    p.firstname, p.lastname, c.contact_type, c.contact_value
FROM      contact c
LEFT JOIN person p  ON p.id = c.person_id  -- identical meaning: LEFT OUTER JOIN ...
ORDER BY  p.lastname, p.firstname, c.contact_type DESC, c.contact_value;
```

What's the difference? We've changed the order of the table names. Note that we're still using a LEFT join, but because *contact* is now the "left" referent (the object in the FROM clause), *contact* data will now be considered as being of primary importance; therefore, all the contact rows will appear in the result - along with any corresponding information that may exist in the person table. As it happens, in the database we're using, every contact record corresponds to a person record so, in this case, it works out that the results are equivalent to what they'd have been if we'd used an inner join. Yet they're different from those of the previous left-join example.

### Right (outer) Join

The right join obeys the same rules as the left join, but in reverse. Now, every record from the table referenced in the join clause will appear in the result, including those that have no corresponding record in the other table. Again, the DBMS supplies each empty right-column cell with the null special marker. The only difference is that the evaluation sequence of tables is carried out in reverse or, in other words, with the roles of the two tables swapped.

```sql
-- A list of ALL contact records with any corresponding person data, even if s
SELECT     p.firstname, p.lastname, c.contact_type, c.contact_value
FROM       person p
RIGHT JOIN contact c ON p.id = c.person_id  -- same as RIGHT OUTER JOIN ...
ORDER BY   p.lastname, p.firstname, c.contact_type DESC, c.contact_value;
```

### Full (outer) Join

A full join retrieves every row of both the left table and the right table, regardless of whether a corresponding record exists in the respective opposite table.

```sql
SELECT    p.firstname, p.lastname, c.contact_type, c.contact_value
FROM      person p
FULL JOIN contact c ON p.id = c.person_id  -- identical meaning: FULL OUTER JOIN ...
ORDER BY  p.lastname, p.firstname, c.contact_type DESC, c.contact_value;
```

Given *table_1* and *table_2* below,

*table_1*

| ID | X |
| --- | --- |
| 1 | 11 |
| 2 | 12 |
| 3 | 13 |

*table_2*

| ID | TABLE_1_ID | Y |
| --- | --- | --- |
| 1 | 1 | 21 |
| 2 | 5 | 22 |

the full join:

```sql
SELECT    *
FROM      table_1 t1
FULL JOIN table_2 t2 ON t1.id = t2.table_1_id;
```

will yield:

| T1.ID | T1.X | T2.ID | T2.TABLE_1_ID | T2.Y |
| --- | --- | --- | --- | --- |
| 1 | 11 | 1 | 1 | 21 |
| 2 | 12 | null | null | null |
| 3 | 13 | null | null | null |
| null | null | 2 | 5 | 22 |

These results contain the (single) matching row, plus a row each for all the other records of both of the original tables. As each of these other rows represent data found in only one of the tables, they are each missing some data, so the cells representative of that missing data contain the null special marker.

Note: The full join is not supported by all DBMS. Nevertheless, because it isn't an atomic operation, it is always possible to create the desired result by a combination of multiple SELECTs with SET operations.

## Cartesian Product (Cross Join)

With inner joins it is possible to omit the ON. SQL interprets this as a - syntactically correct - request to combine every record of the left table with every record of the right table. It will return a large number of rows: the product of the row counts of the two tables.

This particular kind of an inner join is called a Cartesian product or CROSS JOIN. The Cartesian product is an elementary operation of relational algebra, which is the foundation for all rDBMS implementations.

```sql
-- all persons combined with all contacts (some implementations replace the
-- keyword 'JOIN' with a comma)
SELECT p.firstname, p.lastname, c.contact_type, c.contact_value
FROM   person p
JOIN   contact c   -- missing ON keyword: p X c will be created
ORDER BY p.lastname, p.firstname, c.contact_type DESC, c.contact_value;

-- count the resulting rows
SELECT count(*)
FROM   person p
JOIN   contact c;
```

Be careful then; if you unintentionally omit the ON term, the result will be much larger than expected. If, for example, the first table contains 10,000 records, and the second one 20,000 records, the output will contain 200 million rows.

## The n:m Situation

How can we create a list of persons and their hobbies? Remember: one person may run many hobbies and several persons may run the same hobby. So there is no direct connection from persons to hobbies. Between the two tables, we have created a third one *person_hobby*. It holds the id of persons as well as the id of hobbies.

We have to 'walk' from *person* to *person_hobby* and from there to *hobby*.

```sql
-- persons combined with their hobbies
SELECT p.id p_id, p.firstname, p.lastname, h.hobbyname, h.id h_id
FROM   person       p
JOIN   person_hobby ph ON p.id = ph.person_id
JOIN   hobby        h  ON ph.hobby_id = h.id
ORDER BY p.lastname, p.firstname, h.hobbyname;
```

Please note that no column of the table *person_hobby* goes to the result. This table acts only during intermediate execution steps. Even its column *id* is not of interest.

Some people do not perform a hobby. As we performed an INNER JOIN they are not part of the above list. If we want to see in the list also persons without hobbies, we must do what we have done before: use LEFT OUTER JOINs instead of INNER JOINs.

```sql
-- ALL persons plus their hobbies (if present)
SELECT p.id p_id, p.firstname, p.lastname, h.hobbyname, h.id h_id
FROM   person            p
LEFT JOIN   person_hobby ph ON p.id = ph.person_id
LEFT JOIN   hobby        h  ON ph.hobby_id = h.id
ORDER BY p.lastname, p.firstname, h.hobbyname;
```

Hint: If necessary, we can combine every kind of join with every other kind of join in every desired sequence, e.g.: LEFT OUTER with FULL OUTER with INNER ... .

## More Details

Criteria for join operations are not restricted to the usual formulation:

```sql
SELECT ...
FROM   table_1 t1
JOIN   table_2 t2 ON t1.id = t2.fk
...
```

First, we can use **any column**, not only primary key and foreign key columns. In one of the above examples, we used the lastname for a join. Lastname is of type character and has no meaning of any key. To avoid poor performance, some DBMS restrict the use of columns to those having an index.

Second, the comparator is not restricted to the **equal sign**. We can use any meaningful operator, for example, the 'greater than' for numeric values.

```sql
-- Which person has the greater body weight - restricted to 'de Winter' for clarity
SELECT p1.id, p1.firstname as "is heavier", p1.weight, p2.id, p2.firstname as "than", p2.weight
FROM   person p1
JOIN   person p2 ON p1.weight > p2.weight
WHERE  p1.lastname = 'de Winter'
AND    p2.lastname = 'de Winter'
ORDER BY p1.weight desc, p2.weight desc;
```

Third, we can use an **arbitrary function**.

```sql
-- short lastnames vs. long lastnames
SELECT p1.firstname, p1.lastname as "shorter lastname", p2.firstname, p2.lastname
FROM   person p1
JOIN   person p2 ON LENGTH(p1.lastname) < LENGTH(p2.lastname)
-- likewise ORDER BY can use functions
ORDER BY length(p1.lastname), length(p2.lastname);
```

## Exercises

**Exercise:** Show first- and lastname plus icq number for persons having an icq number

**Solution:**

```sql
SELECT p.id, p.firstname, p.lastname, c.contact_value
FROM   person p
JOIN   contact c ON p.id = c.person_id
WHERE  c.contact_type = 'icq';
```

**Exercise:** Show first- and lastname plus ICQ number plus fixed line number for persons having an ICQ number AND a fixed line. You need to join the *contact* table twice.

**Solution:**

```sql
SELECT p.id, p.firstname, p.lastname,
       c1.contact_value as icq,
       c2.contact_value as "fixed line"   -- looks like previous, but is different
FROM   person p
JOIN   contact c1 ON p.id = c1.person_id
JOIN   contact c2 ON p.id = c2.person_id  -- it's a second (virtual) incarnation of contact table
WHERE  c1.contact_type = 'icq'            -- from first incarnation
AND    c2.contact_type = 'fixed line';    -- from second incarnation

-- In this example of an INNER JOIN we can convert the WHERE part to an additional JOIN criterion.
-- This may clarify the intention of the command. But be careful: This shifting in combination with
-- one of the OUTER JOINs may lead to different results.
SELECT p.id, p.firstname, p.lastname, c1.contact_value as icq, c2.contact_value as "fixed line"
FROM   person p
JOIN   contact c1 ON p.id = c1.person_id AND c1.contact_type = 'icq' 
JOIN   contact c2 ON p.id = c2.person_id AND c2.contact_type = 'fixed line';
```

**Exercise:** Show first- and lastname plus (if present) the ICQ number for ALL persons

**Solution:**

```sql
-- To retrieve ALL persons, it's necessary to use a LEFT join.
-- But the first approach is not what we expect! In this example, the LEFT JOIN is evaluated first
-- and creates an intermediate table with null-values in contact_type (eliminate the
-- WHERE clause to see this intermediate result). These rows and all other except the 
-- one with 'ICQ' are then thrown away by evaluating the WHERE clause.
SELECT    p.id, p.firstname, p.lastname, c.contact_value
FROM      person p
LEFT JOIN contact c ON p.id = c.person_id
WHERE     c.contact_type = 'icq';
-- It's necessary to formulate the search criterion as part of the JOIN. Unlike with
-- the INNER JOIN in the previous example with (LEFT/FULL/RIGHT) OUTER JOINs it is not possible 
-- to shift it to the WHERE clause.
SELECT    p.id, p.firstname, p.lastname, c.contact_value
FROM      person p
LEFT JOIN contact c ON p.id = c.person_id AND c.contact_type = 'icq';
```

**Exercise:** Create a list which contains ALL hobbies plus according persons (if present)

**Solution:**

```sql
SELECT p.id p_id, p.firstname, p.lastname, h.hobbyname, h.id h_id
FROM   person              p
RIGHT  JOIN   person_hobby ph ON p.id = ph.person_id
RIGHT  JOIN   hobby        h  ON ph.hobby_id = h.id
ORDER BY h.hobbyname, p.lastname, p.firstname;
```

**Exercise:** Is it possible that one of the three outer joins contains fewer rows than the corresponding inner join?

**Solution:**

No.

All four join types contain the same rows with column-matching-values. In addition
outer joins contain rows where column values do not match - if such a situation exists.
