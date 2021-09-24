UPDATE session SET
  target = 'groundmass'
WHERE target = 'gmass';

UPDATE session SET
  target = 'plagioclase'
WHERE target = 'plag';

/*
Accept all total fusion ages
that are explicitly part of
a total fusion experiment
(we might want to move this to within
the logic of the import script if we
want to be able to adjust what is
considered 'accepted').
*/
UPDATE datum SET
	is_accepted = true
WHERE id IN (
SELECT d.id
FROM datum d
JOIN datum_type dt
  ON dt.id = d.type
JOIN analysis a
  ON a.id = d.analysis
JOIN session s
  ON s.id = a.session_id
WHERE analysis_type = 'Total Fusion Age'
  AND technique = 'Ar/Ar Fusion'
  AND parameter = 'total_fusion_age'
);

/*
Likewise, adjust all plateau ages to be accepted.
*/
UPDATE datum SET
	is_accepted = true
WHERE id IN (
	SELECT d.id
	FROM datum d
	JOIN datum_type dt
	  ON dt.id = d.type
	JOIN analysis a
	  ON a.id = d.analysis
	JOIN session s
	  ON s.id = a.session_id
	WHERE analysis_type = 'Age Plateau'
	  AND technique = 'Ar/Ar Incremental Heating'
	  AND parameter = 'plateau_age'
);
