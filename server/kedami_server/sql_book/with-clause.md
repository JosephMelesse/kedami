# with clause

The `WITH clause` extends SELECT, UPDATE, INSERT or DELETE statements with the definition of one or more 'inline views'. The scope of such 'inline views' is limited to the actual statement. Hence they have a temporary nature. Their purpose is the rearrangement of complex statements in such a way that the intention of the complete statement gets more clearly represented. Primarily, it is a syntax element to support the maintenance of database applications. Secondarily, if complex statements contain identical phrases at different places, and they are rearranged by a single `WITH clause`, the DBMS has a better chance to find an optimal execution strategy.

In other words: The `WITH clause` does not offer any new feature - with the exception of recursive queries, which will be explained in the next chapter. It offers only a syntax element to express complex queries in a clearly arranged way.

Hint: *WITH clause* is the terminology of the SQL standard. In everyday speech, this language construct is mostly referred to as *Common Table Expression (CTE)* and sometimes as *Inline View*. Oracle calls it *Subquery Factoring Clause*. Even though it is not the official term, on this page of the Wikibook, we prefer the term *CTE* as it is an expressive abbreviation.

## Syntax

```sql
WITH cte_1 [(temp_column_name [,...])] AS 
  (SELECT ...)
SELECT ... FROM cte_1
; -- consider the semicolon: the SELECT command (containing a WITH clause) runs from the term 'WITH' up to here.
```

The keyword WITH introduces the definition of a CTE. First, the CTE gets an arbitrary name - 'cte_1' in our case. This is followed by a SELECT statement, which defines how to retrieve data from one or more tables into the CTE (please consider: it's only a definition - it is not necessary, that the data really is materialized in the CTE). Afterward, a normal SELECT, UPDATE, INSERT, or DELETE statement follows, where the previous defined name of the CTE is used directly in the FROM or at any other place, where view or table names are allowed.

## Examples

The first example is limited to report only the content of a *CTE*. In this case it contains information about days where more than one person is born and consists of rows with the date plus a counter.

```sql
-- define the CTE 'ambiguous_date'
WITH ambiguous_date AS  -- this is similar to: CREATE VIEW ambiguous_date AS ...
(SELECT count(*) AS cnt_per_date, date_of_birth
  FROM person
  GROUP BY date_of_birth
  HAVING count(*) > 1
)
-- use the CTE 'ambiguous_date'
SELECT *
  FROM ambiguous_date
;
-- After the semicolon, the CTE is no longer known by the DBMS. It is gone out of scope.
```

The similarity between *CTE*s and views is obvious. The main difference is that view definitions keep alive after using the view name in a statement, whereas the scope of a *CTE* is limited to the statement, where it is defined. This is the reason why some people denote *CTE*s as *Inline Views*.

The second example uses the *CTE* within a SUBSELECT of the main SELECT. The CTE is further modified by a BETWEEN criterion.

```sql
-- define the CTE
WITH ambiguous_date AS
(SELECT count(*) AS cnt_per_date, date_of_birth
  FROM person
  GROUP BY date_of_birth
  HAVING count(*) > 1
)
-- the main SELECT
SELECT *
  FROM person p
  WHERE p.date_of_birth IN
    -- use the CTE
    (SELECT date_of_birth
      FROM ambiguous_date
      --  one can manipulate the CTE in the same manner as every other view or table
      WHERE cnt_per_date BETWEEN 3 AND 10
    )
;
```

The third example uses the *CTE* at different places within the statement.

```sql
-- define the CTE
WITH ambiguous_date AS
(SELECT count(*) AS cnt_per_date, date_of_birth
  FROM person
  GROUP BY date_of_birth
  HAVING count(*) > 1
)
-- use of the CTE at different places and for different purposes
SELECT p.*, (SELECT count(*) AS sum_of_ambiguity_dates
               FROM ambiguous_date
            ) AS number_of_ambiguous_dates
  FROM person p
  WHERE p.date_of_birth IN 
       (SELECT date_of_birth
          FROM ambiguous_date
       )
;
```

The main SELECT retrieves all persons (more than two rows), which have the same birthdays as such identified by the *CTE* (two rows). And it amends every person with the number of ambiguous birthdays (which is '2').

## Extension

The `WITH clause` is the basis for recursive queries, which will be explained in the next chapter.
