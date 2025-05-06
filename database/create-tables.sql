-- public.cargomanifest definition

-- Drop table

-- DROP TABLE public.cargomanifest;

CREATE TABLE public.cargomanifest (
	slot int4 NOT NULL,
	pos_x int4 NULL,
	pos_y int4 NULL,
	state public."ship_slot_state" NULL,
	container_id int4 NULL,
	ship_id int4 NOT NULL,
	CONSTRAINT cargomanifest_pkey PRIMARY KEY (slot, ship_id)
);


-- public.container definition

-- Drop table

-- DROP TABLE public.container;

CREATE TABLE public.container (
	container_id int4 NOT NULL,
	weight float4 NULL,
	CONSTRAINT container_pkey PRIMARY KEY (container_id)
);


-- public.machine definition

-- Drop table

-- DROP TABLE public.machine;

CREATE TABLE public.machine (
	machine_id serial4 NOT NULL,
	"name" text NULL,
	CONSTRAINT machine_pkey PRIMARY KEY (machine_id)
);


-- public.quantity definition

-- Drop table

-- DROP TABLE public.quantity;

CREATE TABLE public.quantity (
	"name" text NOT NULL,
	symbol text NULL,
	unit text NULL,
	CONSTRAINT quantity_pkey PRIMARY KEY (name)
);


-- public.ship definition

-- Drop table

-- DROP TABLE public.ship;

CREATE TABLE public.ship (
	id serial4 NOT NULL,
	roll float4 NULL,
	draft float4 NULL,
	CONSTRAINT pk_id PRIMARY KEY (id)
);


-- public.quay definition

-- Drop table

-- DROP TABLE public.quay;

CREATE TABLE public.quay (
	slot int4 NOT NULL,
	pos_x int4 NULL,
	pos_y int4 NULL,
	state public."quay_slot_state" NULL,
	container_id int4 NULL,
	machine_id int4 NOT NULL,
	CONSTRAINT quay_pkey PRIMARY KEY (slot, machine_id),
	CONSTRAINT quay_container_id_fkey FOREIGN KEY (container_id) REFERENCES public.container(container_id)
);


-- public.run definition

-- Drop table

-- DROP TABLE public.run;

CREATE TABLE public.run (
	run_id int4 NOT NULL,
	machine_id int4 NOT NULL,
	starttime timestamptz NULL,
	CONSTRAINT run_pkey PRIMARY KEY (run_id, machine_id),
	CONSTRAINT run_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machine(machine_id) ON DELETE CASCADE ON UPDATE CASCADE
);


-- public.simulation definition

-- Drop table

-- DROP TABLE public.simulation;

CREATE TABLE public.simulation (
	run_id int4 NOT NULL,
	machine_id int4 NOT NULL,
	num_replications int4 NULL,
	CONSTRAINT simulation_pkey PRIMARY KEY (run_id, machine_id),
	CONSTRAINT simulation_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machine(machine_id),
	CONSTRAINT simulation_run_id_machine_id_fkey FOREIGN KEY (run_id,machine_id) REFERENCES public.run(run_id,machine_id) ON DELETE CASCADE ON UPDATE CASCADE
);


-- public.simulationdatapoint definition

-- Drop table

-- DROP TABLE public.simulationdatapoint;

CREATE TABLE public.simulationdatapoint (
	ts timestamp NOT NULL,
	machine_id int4 NOT NULL,
	run_id int4 NOT NULL,
	replication_nr int4 NOT NULL,
	quantity text NOT NULL,
	value float8 NULL,
	CONSTRAINT simulationdatapoint_pkey PRIMARY KEY (ts, replication_nr, run_id, machine_id, quantity),
	CONSTRAINT simulationdatapoint_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machine(machine_id),
	CONSTRAINT simulationdatapoint_quantity_fkey FOREIGN KEY (quantity) REFERENCES public.quantity("name"),
	CONSTRAINT simulationdatapoint_run_id_machine_id_fkey FOREIGN KEY (run_id,machine_id) REFERENCES public.simulation(run_id,machine_id) ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX simulationdatapoint_ts_idx ON public.simulationdatapoint USING btree (ts DESC);

-- Table Triggers

create trigger ts_insert_blocker before
insert
    on
    public.simulationdatapoint for each row execute function _timescaledb_internal.insert_blocker();


-- public.totalnormalizedeuclideandistance definition

-- Drop table

-- DROP TABLE public.totalnormalizedeuclideandistance;

CREATE TABLE public.totalnormalizedeuclideandistance (
	machine_id int4 NOT NULL,
	run_id int4 NOT NULL,
	distance float8 NULL,
	quantity text NOT NULL,
	CONSTRAINT normalizedeuclideandistance_pkey1 PRIMARY KEY (machine_id, run_id, quantity),
	CONSTRAINT normalizedeuclideandistance_machine_id_fkey1 FOREIGN KEY (machine_id) REFERENCES public.machine(machine_id),
	CONSTRAINT normalizedeuclideandistance_quantity_fkey1 FOREIGN KEY (quantity) REFERENCES public.quantity("name"),
	CONSTRAINT normalizedeuclideandistance_run_id_machine_id_fkey1 FOREIGN KEY (run_id,machine_id) REFERENCES public.run(run_id,machine_id) ON DELETE CASCADE ON UPDATE CASCADE
);


-- public.trajectory definition

-- Drop table

-- DROP TABLE public.trajectory;

CREATE TABLE public.trajectory (
	ts timestamptz NOT NULL,
	machine_id int4 NOT NULL,
	run_id int4 NOT NULL,
	quantity text NOT NULL,
	value float8 NULL,
	CONSTRAINT trajectory_pkey PRIMARY KEY (ts, machine_id, run_id, quantity),
	CONSTRAINT trajectory_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machine(machine_id),
	CONSTRAINT trajectory_quantity_fkey FOREIGN KEY (quantity) REFERENCES public.quantity("name"),
	CONSTRAINT trajectory_run_id_machine_id_fkey FOREIGN KEY (run_id,machine_id) REFERENCES public.run(run_id,machine_id) ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX trajectory_ts_idx ON public.trajectory USING btree (ts DESC);

-- Table Triggers

create trigger ts_insert_blocker before
insert
    on
    public.trajectory for each row execute function _timescaledb_internal.insert_blocker();


-- public.frequentistmetric definition

-- Drop table

-- DROP TABLE public.frequentistmetric;

CREATE TABLE public.frequentistmetric (
	machine_id int4 NOT NULL,
	run_id int4 NOT NULL,
	ts timestamptz NOT NULL,
	mu_lower float8 NULL,
	mu_upper float8 NULL,
	error_lower float8 NULL,
	error_upper float8 NULL,
	quantity text NOT NULL,
	CONSTRAINT frequentistmetric_pkey PRIMARY KEY (ts, machine_id, run_id, quantity),
	CONSTRAINT frequentistmetric_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machine(machine_id),
	CONSTRAINT frequentistmetric_quantity_fkey FOREIGN KEY (quantity) REFERENCES public.quantity("name"),
	CONSTRAINT frequentistmetric_run_id_machine_id_fkey FOREIGN KEY (run_id,machine_id) REFERENCES public.run(run_id,machine_id) ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX frequentistmetric_ts_idx ON public.frequentistmetric USING btree (ts DESC);

-- Table Triggers

create trigger ts_insert_blocker before
insert
    on
    public.frequentistmetric for each row execute function _timescaledb_internal.insert_blocker();


-- public.globalfrequentistmetric definition

-- Drop table

-- DROP TABLE public.globalfrequentistmetric;

CREATE TABLE public.globalfrequentistmetric (
	machine_id int4 NOT NULL,
	run_id int4 NOT NULL,
	average_relative_error float8 NULL,
	average_relative_confidence_indicator float8 NULL,
	maximum_relative_error float8 NULL,
	quantity text NOT NULL,
	CONSTRAINT globalfrequentistmetric_pkey PRIMARY KEY (machine_id, run_id, quantity),
	CONSTRAINT globalfrequentistmetric_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machine(machine_id),
	CONSTRAINT globalfrequentistmetric_quantity_fkey FOREIGN KEY (quantity) REFERENCES public.quantity("name"),
	CONSTRAINT globalfrequentistmetric_run_id_machine_id_fkey FOREIGN KEY (run_id,machine_id) REFERENCES public.run(run_id,machine_id) ON DELETE CASCADE ON UPDATE CASCADE
);


-- public.mahalanobisdistance definition

-- Drop table

-- DROP TABLE public.mahalanobisdistance;

CREATE TABLE public.mahalanobisdistance (
	machine_id int4 NOT NULL,
	run_id int4 NOT NULL,
	distance float8 NULL,
	quantity text NOT NULL,
	CONSTRAINT mahalanobisdistance_pkey PRIMARY KEY (machine_id, run_id, quantity),
	CONSTRAINT mahalanobisdistance_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machine(machine_id),
	CONSTRAINT mahalanobisdistance_quantity_fkey FOREIGN KEY (quantity) REFERENCES public.quantity("name"),
	CONSTRAINT mahalanobisdistance_run_id_machine_id_fkey FOREIGN KEY (run_id,machine_id) REFERENCES public.run(run_id,machine_id) ON DELETE CASCADE ON UPDATE CASCADE
);


-- public.measurement definition

-- Drop table

-- DROP TABLE public.measurement;

CREATE TABLE public.measurement (
	ts timestamp NOT NULL,
	machine_id int4 NOT NULL,
	run_id int4 NOT NULL,
	quantity text NOT NULL,
	value float8 NULL,
	CONSTRAINT measurement_pkey PRIMARY KEY (run_id, ts, machine_id, quantity),
	CONSTRAINT measurement_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machine(machine_id),
	CONSTRAINT measurement_quantity_fkey FOREIGN KEY (quantity) REFERENCES public.quantity("name"),
	CONSTRAINT measurement_run_id_machine_id_fkey FOREIGN KEY (run_id,machine_id) REFERENCES public.run(run_id,machine_id) ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX measurement_ts_idx ON public.measurement USING btree (ts DESC);
CREATE INDEX measurement_ts_machine_id_quantity_run_id_idx ON public.measurement USING btree (ts, machine_id, quantity, run_id);

-- Table Triggers

create trigger ts_insert_blocker before
insert
    on
    public.measurement for each row execute function _timescaledb_internal.insert_blocker();


-- public.normalizedeuclideandistance definition

-- Drop table

-- DROP TABLE public.normalizedeuclideandistance;

CREATE TABLE public.normalizedeuclideandistance (
	machine_id int4 NOT NULL,
	run_id int4 NOT NULL,
	ts timestamptz NOT NULL,
	distance float8 NULL,
	quantity text NOT NULL,
	CONSTRAINT normalizedeuclideandistance_pkey PRIMARY KEY (ts, machine_id, run_id, quantity),
	CONSTRAINT normalizedeuclideandistance_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machine(machine_id),
	CONSTRAINT normalizedeuclideandistance_quantity_fkey FOREIGN KEY (quantity) REFERENCES public.quantity("name"),
	CONSTRAINT normalizedeuclideandistance_run_id_machine_id_fkey FOREIGN KEY (run_id,machine_id) REFERENCES public.run(run_id,machine_id) ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX normalizedeuclideandistance_ts_idx ON public.normalizedeuclideandistance USING btree (ts DESC);

-- Table Triggers

create trigger ts_insert_blocker before
insert
    on
    public.normalizedeuclideandistance for each row execute function _timescaledb_internal.insert_blocker();


-- public.reliabilitymetric definition

-- Drop table

-- DROP TABLE public.reliabilitymetric;

CREATE TABLE public.reliabilitymetric (
	machine_id int4 NOT NULL,
	run_id int4 NOT NULL,
	ts timestamptz NOT NULL,
	interval_bounds float8 NULL,
	value float8 NULL,
	quantity text NOT NULL,
	CONSTRAINT reliabilitymetric_pkey PRIMARY KEY (ts, machine_id, run_id, quantity),
	CONSTRAINT reliabilitymetric_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machine(machine_id),
	CONSTRAINT reliabilitymetric_quantity_fkey FOREIGN KEY (quantity) REFERENCES public.quantity("name"),
	CONSTRAINT reliabilitymetric_run_id_machine_id_fkey FOREIGN KEY (run_id,machine_id) REFERENCES public.run(run_id,machine_id) ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX reliabilitymetric_ts_idx ON public.reliabilitymetric USING btree (ts DESC);

-- Table Triggers

create trigger ts_insert_blocker before
insert
    on
    public.reliabilitymetric for each row execute function _timescaledb_internal.insert_blocker();


-- public.rootmeansquarederror definition

-- Drop table

-- DROP TABLE public.rootmeansquarederror;

CREATE TABLE public.rootmeansquarederror (
	machine_id int4 NOT NULL,
	run_id int4 NOT NULL,
	ts timestamptz NOT NULL,
	distance float8 NULL,
	quantity text NOT NULL,
	CONSTRAINT rootmeansquarederror_pkey PRIMARY KEY (ts, machine_id, run_id, quantity),
	CONSTRAINT rootmeansquarederror_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machine(machine_id),
	CONSTRAINT rootmeansquarederror_quantity_fkey FOREIGN KEY (quantity) REFERENCES public.quantity("name"),
	CONSTRAINT rootmeansquarederror_run_id_machine_id_fkey FOREIGN KEY (run_id,machine_id) REFERENCES public.run(run_id,machine_id) ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX rootmeansquarederror_ts_idx ON public.rootmeansquarederror USING btree (ts DESC);

-- Table Triggers

create trigger ts_insert_blocker before
insert
    on
    public.rootmeansquarederror for each row execute function _timescaledb_internal.insert_blocker();