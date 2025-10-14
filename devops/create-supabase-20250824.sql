-- ********************************************************************
-- tables
-- ********************************************************************


-- Create datasheets_output table
CREATE TABLE public.datasheets_output (
    id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    datasheet_id UUID NOT NULL,
    user_owner UUID NOT NULL,
    code TEXT,
    data JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    FOREIGN KEY (datasheet_id) REFERENCES public.datasheets(id) ON DELETE CASCADE
);

-- Enable Row Level Security
ALTER TABLE public.datasheets_output ENABLE ROW LEVEL SECURITY;


-- ********************************************************************
-- Add unique constraints to ensure name uniqueness per user
-- ********************************************************************

-- Projects: Each user can only have one project with a given name
ALTER TABLE projects
ADD CONSTRAINT unique_user_project_name
UNIQUE (user_owner, name);

-- Datasets: Each user can only have one dataset with a given name
ALTER TABLE datasets
ADD CONSTRAINT unique_user_dataset_name
UNIQUE (user_owner, project_id, name);

-- Charts: Each user can only have one chart with a given name
ALTER TABLE charts
ADD CONSTRAINT unique_user_chart_name
UNIQUE (user_owner, project_id, name);

-- Datasheets: Each user can only have one datasheet with a given name within the same dataset
ALTER TABLE datasheets
ADD CONSTRAINT unique_user_dataset_datasheet_name
UNIQUE (user_owner, dataset_id, name);

ALTER TABLE datasheets_output
ADD CONSTRAINT unique_user_datasheets_output
UNIQUE (user_owner, datasheet_id);


-- ********************************************************************
-- Create function to auto-create default datasheet
-- ********************************************************************
-- Fix security issue: Set search path for the function
CREATE OR REPLACE FUNCTION create_default_datasheet()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO datasheets (name, user_owner, dataset_id, type, created_at, updated_at)
    VALUES ('data', NEW.user_owner, NEW.id, 'table', now(), now());

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public';

-- ********************************************************************
-- Create function to auto-create default datasets
-- ********************************************************************

-- Create trigger to call the function
CREATE TRIGGER auto_create_datasheet
    AFTER INSERT ON datasets
    FOR EACH ROW
    EXECUTE FUNCTION create_default_datasheet();


-- Create function to auto-create default datasets when a project is created
CREATE OR REPLACE FUNCTION public.create_default_datasets()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
BEGIN
    -- Create scratchpad dataset
    INSERT INTO datasets (name, user_owner, project_id, created_at, updated_at)
    VALUES ('scratchpad', NEW.user_owner, NEW.id, now(), now());

    -- Create view dataset
    INSERT INTO datasets (name, user_owner, project_id, created_at, updated_at)
    VALUES ('view', NEW.user_owner, NEW.id, now(), now());

    RETURN NEW;
END;
$function$;

-- Create trigger to automatically create default datasets after project creation
CREATE TRIGGER create_default_datasets_trigger
    AFTER INSERT ON public.projects
    FOR EACH ROW
    EXECUTE FUNCTION public.create_default_datasets();
