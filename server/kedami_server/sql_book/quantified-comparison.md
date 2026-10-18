# Quantified Comparison

There are use cases in which an application wants to compare rows or columns not with a fixed value - e.g.: 'WHERE status = 5' - but with a result of a query which is evaluated at runtime. A first example of such dynamic queries are subqueries which return exactly **one** value: '... WHERE version = (SELECT MAX(version) ...)'. Additionally, sometimes there is the need to compare against a set, which contains **multiple** values: '... WHERE version <comparison> (SELECT version FROM t1 WHERE status > 2 ...)'.

To do so, SQL offers some special comparison methods between the table to be queried and the result of the subquery: IN, ALL, ANY/SOME, and EXISTS. They belong to the group of so-called *predicates*.
* The IN predicate retrieves rows that correlate to the resulting values of the subquery.
* The ALL predicate (in combination with <, <=, =, >=, > or <>) retrieves rows which correlate to **all** values of the subquery (boolean AND operation).
* The ANY predicate (in combination with <, <=, =, >=, > or <>) retrieves rows which correlate to **any** value of the subquery (boolean OR operation). The keyword SOME can be used as a synonym for ANY, so you can exchange one against the other.
* The EXISTS predicate retrieves rows, if the subquery retrieves one or more rows.

## IN

The IN predicate - as described in  a previous chapter - accepts a set of values or rows.

```sql
SELECT * 
FROM   person 
WHERE  id IN 
  (SELECT person_id FROM contact); -- Subquery with potentially a lot of rows.
```

The subquery selects a lot of values. Therefore it is not possible to use operators like '=' or '>'. They would merely compare single values​​. But the IN predicate handles the situation and compares *person.id* with every value of *contact.person_id* regardless of the number of *contact.person_id* values. This comparisons are mutually linked in the sense of boolean OR operations.

The IN predicate can be negated by adding the keyword NOT.

```sql
...
WHERE  id NOT IN
... 
```

## ALL

The ALL predicate compares every row in the sense of a boolean AND with every value of the subquery. It needs - in contrast to the IN predicate - an additional operator, which is one of: <, <=, =, >=, > or <>.

```sql
SELECT *
FROM   person 
WHERE  weight > ALL  
  (SELECT weight FROM person where lastname = 'de Winter');
```

Common hint: If there is no NULL special marker in the subquery it is possible to replace the ALL predicate by equivalent (and more intuitive) operations:

| <op> ALL | Substitution |
| --- | --- |
| < ALL | < (SELECT MIN() ...) |
| <= ALL | <= (SELECT MIN() ...) |
| = ALL | '=' or 'IN', if subselect retrieves 1 value. |
| Else: A single value cannot be equal to different values at the same time. (x = a AND x = b) evaluates to 'false' in all cases. |  |
| >= ALL | >= (SELECT MAX() ...) |
| > ALL | > (SELECT MAX() ...) |
| <> ALL | '<>' or 'NOT IN', if subselect retrieves 1 value. |
| Else: 'NOT IN'. (x <> a AND x <> b). |  |

MySQL hint: Because of query rewrite issues the ONLY_FULL_GROUP_BY mode shall be disabled, e.g. by the command: set sql_mode='ANSI'.

## ANY/SOME

The key words ANY and SOME are synonyms, their meaning is the same. Within this Wikibook, we prefer the use of ANY.

The ANY predicate compares every row in the sense of a boolean OR with every value of the subquery. It needs - in contrast to the IN predicate - an additional operator, which is one of: <, <=, =, >=, > or <>.

```sql
SELECT *
FROM   person 
WHERE  weight > ANY  
  (SELECT weight FROM person where lastname = 'de Winter');
```

Common hint: If there is no NULL special marker in the subquery it is possible to replace the ANY predicate by equivalent (and more intuitive) operations:

| <op> ANY | Substitution |
| --- | --- |
| < ANY | < (SELECT MAX() ...) |
| <= ANY | <= (SELECT MAX() ...) |
| = ANY | '=' or 'IN', if subselect retrieves 1 value. |
| Else: 'IN'. (x = a OR x = b). |  |
| >= ANY | >= (SELECT MIN() ...) |
| > ANY | > (SELECT MIN() ...) |
| <> ANY | '<>' or 'NOT IN', if subselect retrieves 1 value. |
| Else: A single value is always different from two or more different values under an OR conjunction. (x <> a OR x <> b) evaluates to 'true' in all cases. |  |

MySQL hint: Because of query rewrite issues the ONLY_FULL_GROUP_BY mode shall be disabled, e.g. by the command: set sql_mode='ANSI'.

## EXISTS

The EXISTS predicate retrieves rows, if the subquery retrieves one or more rows. Meaningful examples typically use a correlated subquery.

```sql
SELECT *
FROM   contact c1
WHERE EXISTS
  (SELECT  *
   FROM    contact c2
   WHERE   c2.person_id = c1.person_id  -- correlation criterion between query and subquery
   AND     c2.contact_type = 'icq');
```

The example retrieves all contacts for such persons, which have an ICQ-contact.

The EXISTS predicate can be negated by adding the keyword NOT.

```sql
...
WHERE NOT EXISTS
... 
```
